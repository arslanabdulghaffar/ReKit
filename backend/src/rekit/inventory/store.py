"""Atomic reservations, operator completion, and audit in the evidence SQLite file."""

from datetime import UTC, datetime
import json
import sqlite3
from uuid import uuid4

from pydantic import BaseModel, TypeAdapter

from rekit.catalog.models import Catalog, Identifier, VisibleCondition
from rekit.evidence.models import VerificationState
from rekit.evidence.store import ConflictError, EvidenceStore, NotFoundError, _canonical
from rekit.inventory.execution import (
    ApprovalCommand, AuditRecord, Availability, CancellationCommand, CompletedKit,
    CompletionCommand, InventoryEntry, InventorySnapshot, PlanState, StoredPlan,
)
from rekit.inventory.models import InventoryEligibility, InventoryItem
from rekit.recovery.models import (
    DispositionPolicy, EconomicScenario, RecoveryActionKind,
    RecoveryPlan, RecoveryProblem, ReturnContents, SolveStatus, SolverSettings,
)
from rekit.recovery.planner import evaluate_selection, problem_fingerprint, solve_recovery


_CONSUMING = {RecoveryActionKind.REBUILD, RecoveryActionKind.SALVAGE, RecoveryActionKind.LIQUIDATE}
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS recovery_plans (
        plan_id TEXT PRIMARY KEY NOT NULL,
        proposal_json TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS recovery_plan_states (
        plan_id TEXT PRIMARY KEY NOT NULL REFERENCES recovery_plans(plan_id),
        version INTEGER NOT NULL CHECK (version >= 1),
        state TEXT NOT NULL CHECK (state IN ('proposed', 'approved', 'cancelled', 'completed')),
        completed_action_ids TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS component_allocations (
        physical_component_id TEXT PRIMARY KEY NOT NULL REFERENCES physical_components(physical_component_id),
        plan_id TEXT NOT NULL REFERENCES recovery_plans(plan_id),
        action_id TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN ('reserved', 'consumed'))
    )""",
    "CREATE INDEX IF NOT EXISTS allocations_by_plan ON component_allocations(plan_id, action_id)",
    """CREATE TABLE IF NOT EXISTS recovery_operations (
        operation_id TEXT PRIMARY KEY NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('proposed', 'approved', 'cancelled', 'action_completed')),
        plan_id TEXT NOT NULL REFERENCES recovery_plans(plan_id),
        action_id TEXT,
        payload TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS action_completions (
        plan_id TEXT NOT NULL REFERENCES recovery_plans(plan_id),
        action_id TEXT NOT NULL,
        operation_id TEXT NOT NULL UNIQUE REFERENCES recovery_operations(operation_id),
        payload TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        PRIMARY KEY (plan_id, action_id)
    )""",
    """CREATE TABLE IF NOT EXISTS completed_kits (
        completed_kit_id TEXT PRIMARY KEY NOT NULL,
        plan_id TEXT NOT NULL,
        action_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        UNIQUE (plan_id, action_id),
        FOREIGN KEY (plan_id, action_id) REFERENCES action_completions(plan_id, action_id)
    )""",
    """CREATE TABLE IF NOT EXISTS inventory_audit (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id TEXT NOT NULL REFERENCES recovery_plans(plan_id),
        operation_id TEXT NOT NULL UNIQUE REFERENCES recovery_operations(operation_id),
        operator_id TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('proposed', 'approved', 'cancelled', 'action_completed')),
        plan_version INTEGER NOT NULL CHECK (plan_version >= 1),
        reason TEXT NOT NULL,
        recorded_at TEXT NOT NULL,
        action_id TEXT
    )""",
    """CREATE TRIGGER IF NOT EXISTS consumed_allocation_no_delete BEFORE DELETE ON component_allocations
        WHEN OLD.state = 'consumed'
        BEGIN SELECT RAISE(ABORT, 'Consumed allocation cannot be removed'); END""",
    """CREATE TRIGGER IF NOT EXISTS allocation_guard BEFORE UPDATE ON component_allocations
        WHEN OLD.state = 'consumed' OR NEW.physical_component_id != OLD.physical_component_id
             OR NEW.plan_id != OLD.plan_id OR NEW.action_id != OLD.action_id
             OR NEW.state != 'consumed'
        BEGIN SELECT RAISE(ABORT, 'Invalid component allocation transition'); END""",
)


class InventoryStore:
    """Use evidence's concrete connection helpers so checks and writes are atomic."""

    def __init__(self, evidence: EvidenceStore, policy: DispositionPolicy) -> None:
        self.evidence = evidence
        self.catalog = Catalog.model_validate(evidence.catalog.model_dump(mode="json", warnings=False))
        self.policy = DispositionPolicy.model_validate(policy.model_dump(mode="json", warnings=False))
        with evidence.transaction() as connection:
            for statement in _SCHEMA:
                connection.execute(statement)
            for table in ("recovery_plans", "recovery_operations", "action_completions", "completed_kits", "inventory_audit"):
                for operation in ("UPDATE", "DELETE"):
                    connection.execute(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                        "BEGIN SELECT RAISE(ABORT, 'Recovery history is append-only'); END"
                    )
            current_policy = connection.execute(
                "SELECT value FROM evidence_metadata WHERE key = 'disposition_policy'"
            ).fetchone()
            if current_policy is None:
                connection.execute(
                    "INSERT INTO evidence_metadata(key, value) VALUES ('disposition_policy', ?)",
                    (_canonical(self.policy),),
                )
            self._authority(connection)

    def _authority(self, connection: sqlite3.Connection, plan: RecoveryPlan | None = None) -> None:
        metadata = dict(connection.execute("SELECT key, value FROM evidence_metadata"))
        if metadata.get("catalog") != _canonical(self.catalog) or self.evidence.catalog != self.catalog:
            raise ConflictError("Current catalog does not match the pinned inventory catalog")
        if metadata.get("disposition_policy") != _canonical(self.policy):
            raise ConflictError("Current disposition policy differs from the pinned policy")
        if plan is not None and (plan.problem.catalog != self.catalog or plan.problem.policy != self.policy):
            raise ConflictError("Plan catalog or disposition policy differs from the approved current policy")

    def _item(self, connection: sqlite3.Connection, component_id: str) -> InventoryItem:
        history = self.evidence._history(connection, component_id)
        eligible = (
            history.current.state == VerificationState.VERIFIED
            and history.current.verification is not None
            and history.current.verification.visible_condition != VisibleCondition.UNKNOWN
        )
        return InventoryItem(
            component=history.component, evidence=history.current,
            eligibility=InventoryEligibility.ELIGIBLE if eligible else InventoryEligibility.HELD,
        )

    @staticmethod
    def _contents(connection: sqlite3.Connection) -> tuple[ReturnContents, ...]:
        members = {}
        for row in connection.execute(
            "SELECT physical_component_id, source_return_id FROM physical_components ORDER BY source_return_id, physical_component_id"
        ):
            members.setdefault(row["source_return_id"], []).append(row["physical_component_id"])
        return tuple(ReturnContents(return_id=return_id, component_ids=tuple(component_ids)) for return_id, component_ids in members.items())

    def _snapshot(self, connection: sqlite3.Connection) -> InventorySnapshot:
        allocations = {
            row["physical_component_id"]: row
            for row in connection.execute("SELECT physical_component_id, plan_id, action_id, state FROM component_allocations")
        }
        entries = []
        for row in connection.execute("SELECT physical_component_id FROM physical_components ORDER BY physical_component_id"):
            item = self._item(connection, row["physical_component_id"])
            allocation = allocations.get(item.component.physical_component_id)
            if allocation is not None:
                entries.append(InventoryEntry(
                    item=item, availability=Availability(allocation["state"]),
                    plan_id=allocation["plan_id"], action_id=allocation["action_id"],
                ))
            else:
                entries.append(InventoryEntry(
                    item=item,
                    availability=Availability.AVAILABLE if item.eligibility == InventoryEligibility.ELIGIBLE else Availability.HELD,
                ))
        kits = tuple(
            CompletedKit.model_validate_json(row["payload"])
            for row in connection.execute("SELECT payload FROM completed_kits ORDER BY completed_kit_id")
        )
        return InventorySnapshot(items=tuple(entries), completed_kits=kits)

    def inventory(self) -> InventorySnapshot:
        with self.evidence._read() as connection:
            return self._snapshot(connection)

    @staticmethod
    def _stored(connection: sqlite3.Connection, plan_id: str) -> StoredPlan:
        row = connection.execute(
            "SELECT p.proposal_json, s.version, s.state, s.completed_action_ids "
            "FROM recovery_plans p JOIN recovery_plan_states s ON s.plan_id = p.plan_id WHERE p.plan_id = ?",
            (plan_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Unknown recovery plan: {plan_id}")
        return StoredPlan(
            plan=RecoveryPlan.model_validate_json(row["proposal_json"]), version=row["version"],
            state=row["state"], completed_action_ids=tuple(json.loads(row["completed_action_ids"])),
        )

    def get_plan(self, plan_id: str) -> StoredPlan:
        with self.evidence._read() as connection:
            return self._stored(connection, plan_id)

    @staticmethod
    def _validate_plan(plan: RecoveryPlan) -> None:
        if problem_fingerprint(plan.problem) != plan.input_hash:
            raise ConflictError("Stored plan input fingerprint does not match its immutable problem")
        if plan.status not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
            raise ConflictError("A plan without a solver-confirmed feasible solution cannot be executed")
        violations = evaluate_selection(plan.problem, plan.selected_actions)
        if violations:
            raise ConflictError(f"Stored plan is not a valid approved allocation: {'; '.join(violations)}")

    @staticmethod
    def _operation(
        connection: sqlite3.Connection, operation_id: str, kind: str,
        plan_id: str, action_id: str | None, command: BaseModel,
    ) -> bool:
        existing = connection.execute(
            "SELECT kind, plan_id, action_id, payload FROM recovery_operations WHERE operation_id = ?", (operation_id,)
        ).fetchone()
        if existing is None:
            return False
        if (existing["kind"], existing["plan_id"], existing["action_id"], existing["payload"]) != (kind, plan_id, action_id, _canonical(command)):
            raise ConflictError(f"Operation ID already belongs to a different request: {operation_id}")
        return True

    @staticmethod
    def _record_operation(
        connection: sqlite3.Connection, operation_id: str, kind: str,
        plan_id: str, action_id: str | None, command: BaseModel,
    ) -> None:
        connection.execute(
            "INSERT INTO recovery_operations(operation_id, kind, plan_id, action_id, payload) VALUES (?, ?, ?, ?, ?)",
            (operation_id, kind, plan_id, action_id, _canonical(command)),
        )

    @staticmethod
    def _append_audit(
        connection: sqlite3.Connection, *, plan_id: str, operation_id: str, operator_id: str,
        kind: str, version: int, reason: str, action_id: str | None = None,
    ) -> None:
        connection.execute(
            "INSERT INTO inventory_audit(plan_id, operation_id, operator_id, kind, plan_version, reason, recorded_at, action_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (plan_id, operation_id, operator_id, kind, version, reason, datetime.now(UTC).isoformat(), action_id),
        )

    def request_plan(
        self, scenario: EconomicScenario, settings: SolverSettings = SolverSettings(),
        *, requested_by: str = "system-planner",
    ) -> StoredPlan:
        requested_by = TypeAdapter(Identifier).validate_python(requested_by)
        scenario = EconomicScenario.model_validate(scenario.model_dump(mode="json", warnings=False))
        settings = SolverSettings.model_validate(settings.model_dump(mode="json", warnings=False))
        with self.evidence._read() as connection:
            self._authority(connection)
            snapshot = self._snapshot(connection)
            problem = RecoveryProblem(
                catalog=self.catalog, policy=self.policy, scenario=scenario,
                inventory=tuple(entry.item for entry in snapshot.items if entry.availability in (Availability.AVAILABLE, Availability.HELD)),
                return_contents=self._contents(connection),
            )
        # No database transaction remains open while the solver runs.
        plan = solve_recovery(problem, settings)
        plan = RecoveryPlan.model_validate(plan.model_dump(mode="json", warnings=False))
        if plan.problem != problem or plan.input_hash != problem_fingerprint(problem):
            raise ConflictError("Planner result does not match the authoritative inventory snapshot")
        if plan.status in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
            self._validate_plan(plan)
        with self.evidence.transaction() as connection:
            self._authority(connection, plan)
            connection.execute("INSERT INTO recovery_plans(plan_id, proposal_json) VALUES (?, ?)", (plan.plan_id, _canonical(plan)))
            connection.execute(
                "INSERT INTO recovery_plan_states(plan_id, version, state, completed_action_ids) VALUES (?, 1, 'proposed', '[]')",
                (plan.plan_id,),
            )
            operation_id = f"proposal:{uuid4()}"
            self._record_operation(connection, operation_id, "proposed", plan.plan_id, None, plan)
            self._append_audit(
                connection, plan_id=plan.plan_id, operation_id=operation_id, operator_id=requested_by,
                kind="proposed", version=1, reason="Generated a recovery proposal using explicit scenario estimates; no inventory was reserved.",
            )
            return self._stored(connection, plan.plan_id)

    @staticmethod
    def _check_version(stored: StoredPlan, expected: int) -> None:
        if stored.version != expected:
            raise ConflictError(f"Stale plan version: expected {expected}, current {stored.version}")

    def _check_evidence(self, connection: sqlite3.Connection, plan: RecoveryPlan, component_ids: set[str]) -> None:
        expected = {item.component.physical_component_id: item for item in plan.problem.inventory}
        for component_id in sorted(component_ids):
            if component_id not in expected or self._item(connection, component_id) != expected[component_id]:
                raise ConflictError(f"Evidence or physical identity changed since planning: {component_id}")

    def _check_membership(self, connection: sqlite3.Connection, plan: RecoveryPlan, return_ids: set[str]) -> None:
        expected = {contents.return_id: set(contents.component_ids) for contents in plan.problem.return_contents}
        current = {contents.return_id: set(contents.component_ids) for contents in self._contents(connection)}
        for return_id in sorted(return_ids):
            if current.get(return_id) != expected.get(return_id):
                raise ConflictError(f"Registered return membership changed since planning: {return_id}")

    @staticmethod
    def _set_state(connection: sqlite3.Connection, stored: StoredPlan, state: PlanState, completed: tuple[str, ...]) -> None:
        updated = connection.execute(
            "UPDATE recovery_plan_states SET version = version + 1, state = ?, completed_action_ids = ? "
            "WHERE plan_id = ? AND version = ? AND state = ?",
            (state.value, json.dumps(completed), stored.plan.plan_id, stored.version, stored.state.value),
        )
        if updated.rowcount != 1:
            raise ConflictError("Recovery plan state changed during the operation")

    def approve(self, plan_id: str, command: ApprovalCommand) -> StoredPlan:
        command = ApprovalCommand.model_validate(command.model_dump(mode="json", warnings=False))
        with self.evidence.transaction() as connection:
            if self._operation(connection, command.operation_id, "approved", plan_id, None, command):
                return self._stored(connection, plan_id)
            stored = self._stored(connection, plan_id)
            self._check_version(stored, command.expected_version)
            if stored.state != PlanState.PROPOSED:
                raise ConflictError("Only a proposed plan can be approved")
            self._authority(connection, stored.plan)
            self._validate_plan(stored.plan)
            component_ids = {item.component.physical_component_id for item in stored.plan.problem.inventory}
            self._check_evidence(connection, stored.plan, component_ids)
            self._check_membership(connection, stored.plan, {contents.return_id for contents in stored.plan.problem.return_contents})
            for component_id in sorted(component_ids):
                if connection.execute("SELECT 1 FROM component_allocations WHERE physical_component_id = ?", (component_id,)).fetchone() is not None:
                    raise ConflictError(f"Physical component is already reserved or consumed: {component_id}")
            consuming = tuple(action for action in stored.plan.selected_actions if action.kind in _CONSUMING)
            for action in consuming:
                for component_id in action.component_ids:
                    connection.execute(
                        "INSERT INTO component_allocations(physical_component_id, plan_id, action_id, state) VALUES (?, ?, ?, 'reserved')",
                        (component_id, plan_id, action.action_id),
                    )
            self._set_state(connection, stored, PlanState.APPROVED if consuming else PlanState.COMPLETED, ())
            self._record_operation(connection, command.operation_id, "approved", plan_id, None, command)
            self._append_audit(
                connection, plan_id=plan_id, operation_id=command.operation_id, operator_id=command.operator_id,
                kind="approved", version=stored.version + 1, reason=command.reason,
            )
            return self._stored(connection, plan_id)

    def cancel(self, plan_id: str, command: CancellationCommand) -> StoredPlan:
        command = CancellationCommand.model_validate(command.model_dump(mode="json", warnings=False))
        with self.evidence.transaction() as connection:
            if self._operation(connection, command.operation_id, "cancelled", plan_id, None, command):
                return self._stored(connection, plan_id)
            stored = self._stored(connection, plan_id)
            self._check_version(stored, command.expected_version)
            if stored.state not in (PlanState.PROPOSED, PlanState.APPROVED):
                raise ConflictError("Only a proposed or approved plan can be cancelled")
            if stored.completed_action_ids:
                raise ConflictError("A partially completed plan cannot be cancelled or undo consumed inventory")
            connection.execute("DELETE FROM component_allocations WHERE plan_id = ? AND state = 'reserved'", (plan_id,))
            self._set_state(connection, stored, PlanState.CANCELLED, ())
            self._record_operation(connection, command.operation_id, "cancelled", plan_id, None, command)
            self._append_audit(
                connection, plan_id=plan_id, operation_id=command.operation_id, operator_id=command.operator_id,
                kind="cancelled", version=stored.version + 1, reason=command.reason,
            )
            return self._stored(connection, plan_id)

    def complete_action(self, plan_id: str, action_id: str, command: CompletionCommand) -> StoredPlan:
        command = CompletionCommand.model_validate(command.model_dump(mode="json", warnings=False))
        with self.evidence.transaction() as connection:
            if self._operation(connection, command.operation_id, "action_completed", plan_id, action_id, command):
                return self._stored(connection, plan_id)
            stored = self._stored(connection, plan_id)
            self._check_version(stored, command.expected_version)
            if stored.state != PlanState.APPROVED:
                raise ConflictError("Completion requires an approved plan with active reservations")
            action = next((candidate for candidate in stored.plan.selected_actions if candidate.action_id == action_id), None)
            if action is None:
                raise NotFoundError(f"Unknown selected recovery action: {action_id}")
            if action.kind not in _CONSUMING:
                raise ConflictError("Hold and retain actions do not consume inventory or create completed kits")
            if action_id in stored.completed_action_ids:
                raise ConflictError("Recovery action has already been completed")
            if set(command.component_ids) != set(action.component_ids):
                raise ConflictError("Completion must confirm exactly the action's reserved physical components")
            if (command.completed_kit_id is not None) != (action.kind == RecoveryActionKind.REBUILD):
                raise ValueError("A completed kit ID is required only for rebuild completion")
            self._authority(connection, stored.plan)
            self._validate_plan(stored.plan)
            self._check_evidence(connection, stored.plan, set(action.component_ids))
            source_returns = {
                item.component.source_return_id for item in stored.plan.problem.inventory
                if item.component.physical_component_id in action.component_ids
            }
            self._check_membership(connection, stored.plan, source_returns)
            reservations = tuple(connection.execute(
                "SELECT physical_component_id, state FROM component_allocations WHERE plan_id = ? AND action_id = ?",
                (plan_id, action_id),
            ))
            if {row["physical_component_id"] for row in reservations} != set(action.component_ids) or any(row["state"] != "reserved" for row in reservations):
                raise ConflictError("Action reservations are missing, consumed, or different from the approved identities")
            updated = connection.execute(
                "UPDATE component_allocations SET state = 'consumed' WHERE plan_id = ? AND action_id = ? AND state = 'reserved'",
                (plan_id, action_id),
            )
            if updated.rowcount != len(action.component_ids):
                raise ConflictError("Reservation count changed during completion")
            self._record_operation(connection, command.operation_id, "action_completed", plan_id, action_id, command)
            completed_at = datetime.now(UTC)
            connection.execute(
                "INSERT INTO action_completions(plan_id, action_id, operation_id, payload, completed_at) VALUES (?, ?, ?, ?, ?)",
                (plan_id, action_id, command.operation_id, _canonical(command), completed_at.isoformat()),
            )
            if action.kind == RecoveryActionKind.REBUILD:
                kit = CompletedKit(
                    completed_kit_id=command.completed_kit_id, plan_id=plan_id, action_id=action_id,
                    configuration_id=action.configuration_id, component_ids=action.component_ids,
                    operator_id=command.operator_id, completed_at=completed_at,
                    evidence_references=command.evidence_references,
                )
                connection.execute(
                    "INSERT INTO completed_kits(completed_kit_id, plan_id, action_id, payload) VALUES (?, ?, ?, ?)",
                    (kit.completed_kit_id, plan_id, action_id, _canonical(kit)),
                )
            completed = tuple(sorted((*stored.completed_action_ids, action_id)))
            all_consuming = {candidate.action_id for candidate in stored.plan.selected_actions if candidate.kind in _CONSUMING}
            state = PlanState.COMPLETED if set(completed) == all_consuming else PlanState.APPROVED
            self._set_state(connection, stored, state, completed)
            self._append_audit(
                connection, plan_id=plan_id, operation_id=command.operation_id, operator_id=command.operator_id,
                kind="action_completed", version=stored.version + 1, reason=command.reason, action_id=action_id,
            )
            return self._stored(connection, plan_id)

    def audit(self, plan_id: str) -> tuple[AuditRecord, ...]:
        with self.evidence._read() as connection:
            self._stored(connection, plan_id)
            return tuple(AuditRecord.model_validate(dict(row)) for row in connection.execute(
                "SELECT sequence, plan_id, operation_id, operator_id, kind, plan_version, reason, recorded_at, action_id "
                "FROM inventory_audit WHERE plan_id = ? ORDER BY sequence", (plan_id,),
            ))
