"""SQLite reservation, approval, completion, and audit behavior under real transactions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Barrier

import pytest

from rekit.catalog.models import Catalog, ComponentIdentity, VisibleCondition
from rekit.evidence.models import (
    AssertionSource,
    Observation,
    OperatorVerification,
    PhysicalComponent,
    ReturnBatch,
    ReturnRecord,
)
from rekit.evidence.store import ConflictError, EvidenceStore, NotFoundError
from rekit.inventory.execution import (
    ApprovalCommand,
    Availability,
    CancellationCommand,
    CompletionCommand,
    PlanState,
    StoredPlan,
)
from rekit.inventory.store import InventoryStore
from rekit.recovery.models import (
    ComponentEconomics,
    DispositionPolicy,
    EconomicScenario,
    KitEconomics,
    RecoveryActionKind,
    ReturnEconomics,
)


NOW = datetime(2026, 10, 13, 20, tzinfo=timezone.utc)


@pytest.fixture
def catalog() -> Catalog:
    path = Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json"
    return Catalog.model_validate_json(path.read_text(encoding="utf-8"))


def add_component(
    evidence: EvidenceStore,
    component_id: str,
    component_type: str,
    *,
    return_id: str | None = None,
    verified: bool = True,
) -> None:
    source_return = return_id or f"return-{component_id}"
    evidence.register_return(ReturnRecord(
        return_id=source_return, batch_id="batch-001", product_family_id="demo-kit", received_at=NOW,
    ))
    evidence.register_component(PhysicalComponent(
        physical_component_id=component_id, source_return_id=source_return, registered_at=NOW,
    ))
    if verified:
        evidence.record_observation(Observation(
            observation_id=f"observation-{component_id}",
            physical_component_id=component_id,
            source_return_id=source_return,
            captured_at=NOW,
            evidence_reference=f"synthetic://evidence/{component_id}",
            source=AssertionSource.OPERATOR,
            source_reference="operator-001",
        ))
        evidence.verify(OperatorVerification(
            verification_id=f"verification-{component_id}",
            physical_component_id=component_id,
            identity=ComponentIdentity(component_type_id=component_type, revision="A"),
            operator_id="operator-001",
            verified_at=NOW,
            evidence_observation_ids=(f"observation-{component_id}",),
            visible_condition=VisibleCondition.ACCEPTABLE,
            reason="Synthetic visible identity and condition verification.",
        ), expected_version=evidence.current(component_id).version)


@pytest.fixture
def evidence(tmp_path: Path, catalog: Catalog) -> EvidenceStore:
    result = EvidenceStore(tmp_path / "inventory.sqlite3", catalog)
    result.register_batch(ReturnBatch(batch_id="batch-001", received_at=NOW))
    add_component(result, "body-001", "body")
    add_component(result, "adapter-001", "adapter")
    return result


@pytest.fixture
def policy() -> DispositionPolicy:
    return DispositionPolicy(
        policy_id="synthetic-disposition-policy", version="1",
        approved_by="operator-001", approved_at=NOW,
    )


def scenario_for(
    evidence: EvidenceStore,
    *,
    donor_value: int = 0,
    kit_price: int = 1000,
    liquidation_values: dict[str, int] | None = None,
    salvage_value: int = 0,
) -> EconomicScenario:
    return EconomicScenario(
        scenario_id="synthetic-scenario",
        description="Invented economics for inventory transaction tests.",
        currency="USD", valuation_date=NOW.date(), labor_cost_per_minute_cents=10,
        kits=(KitEconomics(configuration_id="standard-kit", selling_price_cents=kit_price, labor_minutes=10),),
        components=tuple(ComponentEconomics(
            physical_component_id=item.component.physical_component_id,
            donor_value_cents=donor_value,
            salvage_value_cents=salvage_value,
        ) for item in evidence.inventory_items()),
        returns=tuple(ReturnEconomics(return_id=return_id, liquidation_value_cents=value)
                      for return_id, value in (liquidation_values or {}).items()),
    )


@pytest.fixture
def store(evidence: EvidenceStore, policy: DispositionPolicy) -> InventoryStore:
    return InventoryStore(evidence, policy)


def approval(plan: StoredPlan, operation_id: str = "approve-001") -> ApprovalCommand:
    return ApprovalCommand(
        operation_id=operation_id, operator_id="operator-001",
        expected_version=plan.version, reason="Reviewed the selected components and modeled scenario.",
    )


def cancellation(plan: StoredPlan, operation_id: str = "cancel-001") -> CancellationCommand:
    return CancellationCommand(
        operation_id=operation_id, operator_id="operator-001",
        expected_version=plan.version, reason="Operator cancelled this uncompleted plan.",
    )


def completion(
    plan: StoredPlan,
    action_id: str,
    operation_id: str = "complete-001",
    completed_kit_id: str | None = "completed-kit-001",
) -> CompletionCommand:
    action = next(action for action in plan.plan.selected_actions if action.action_id == action_id)
    return CompletionCommand(
        operation_id=operation_id, operator_id="operator-001", expected_version=plan.version,
        reason="Operator checked exact physical contents and recorded completion evidence.",
        confirmed=True, component_ids=action.component_ids,
        evidence_references=(f"synthetic://completion/{operation_id}",),
        completed_kit_id=completed_kit_id,
    )


def plan_and_approve(store: InventoryStore, evidence: EvidenceStore) -> StoredPlan:
    proposed = store.request_plan(scenario_for(evidence))
    return store.approve(proposed.plan.plan_id, approval(proposed))


def first_rebuild(plan: StoredPlan) -> str:
    return next(action.action_id for action in plan.plan.selected_actions if action.kind is RecoveryActionKind.REBUILD)


def state_snapshot(store: InventoryStore, plan_id: str):
    return store.get_plan(plan_id), store.inventory(), store.audit(plan_id)


def add_new_evidence(evidence: EvidenceStore, component_id: str = "body-001") -> None:
    component = evidence.get_component(component_id)
    evidence.record_observation(Observation(
        observation_id=f"new-observation-{component_id}", physical_component_id=component_id,
        source_return_id=component.source_return_id, captured_at=NOW,
        evidence_reference=f"synthetic://new-view/{component_id}",
        source=AssertionSource.OPERATOR, source_reference="operator-002",
    ))


def test_approval_atomically_reserves_selected_components_and_records_audit(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    assert proposed.state is PlanState.PROPOSED
    assert all(entry.availability is Availability.AVAILABLE for entry in store.inventory().items)
    approved = store.approve(proposed.plan.plan_id, approval(proposed))
    assert approved.state is PlanState.APPROVED
    assert approved.version == proposed.version + 1
    snapshot = store.inventory()
    assert len(snapshot.items) == 2
    assert all(entry.availability is Availability.RESERVED for entry in snapshot.items)
    assert {entry.plan_id for entry in snapshot.items} == {approved.plan.plan_id}
    assert {entry.action_id for entry in snapshot.items} == {first_rebuild(approved)}
    assert [event.kind for event in store.audit(approved.plan.plan_id)] == ["proposed", "approved"]
    assert not snapshot.completed_kits


def test_identical_approval_retry_does_not_duplicate_reservations_or_audit(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    command = approval(proposed)
    approved = store.approve(proposed.plan.plan_id, command)
    before = state_snapshot(store, proposed.plan.plan_id)
    assert store.approve(proposed.plan.plan_id, command) == approved
    assert state_snapshot(store, proposed.plan.plan_id) == before


def test_operation_id_cannot_be_reused_with_changed_payload_or_command_kind(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    command = approval(proposed)
    approved = store.approve(proposed.plan.plan_id, command)
    before = state_snapshot(store, approved.plan.plan_id)
    changed = ApprovalCommand.model_validate(command.model_dump() | {"reason": "Changed instruction"})
    with pytest.raises(ConflictError):
        store.approve(approved.plan.plan_id, changed)
    with pytest.raises(ConflictError):
        store.cancel(approved.plan.plan_id, cancellation(approved, operation_id=command.operation_id))
    assert state_snapshot(store, approved.plan.plan_id) == before


def test_operation_ids_are_global_across_plans(store: InventoryStore, evidence: EvidenceStore) -> None:
    first = store.request_plan(scenario_for(evidence))
    second = store.request_plan(scenario_for(evidence))
    store.approve(first.plan.plan_id, approval(first, "shared-operation"))
    before = state_snapshot(store, second.plan.plan_id)
    with pytest.raises(ConflictError):
        store.approve(second.plan.plan_id, approval(second, "shared-operation"))
    assert state_snapshot(store, second.plan.plan_id) == before


def test_reapproval_with_a_new_operation_cannot_duplicate_an_allocation(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    approved = plan_and_approve(store, evidence)
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(ConflictError):
        store.approve(approved.plan.plan_id, approval(approved, "second-approval"))
    assert state_snapshot(store, approved.plan.plan_id) == before


def test_stale_plan_version_rejects_reservation_without_mutation(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    command = ApprovalCommand.model_validate(approval(proposed).model_dump() | {"expected_version": proposed.version + 1})
    before = state_snapshot(store, proposed.plan.plan_id)
    with pytest.raises(ConflictError):
        store.approve(proposed.plan.plan_id, command)
    assert state_snapshot(store, proposed.plan.plan_id) == before


def test_new_evidence_invalidates_an_unapproved_plan(store: InventoryStore, evidence: EvidenceStore) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    add_new_evidence(evidence)
    before = state_snapshot(store, proposed.plan.plan_id)
    with pytest.raises(ConflictError):
        store.approve(proposed.plan.plan_id, approval(proposed))
    assert state_snapshot(store, proposed.plan.plan_id) == before


@pytest.mark.parametrize("policy_change", [{"version": "2"}, {"approved_by": "different-approver"}])
def test_changed_disposition_policy_invalidates_old_plan(
    store: InventoryStore, evidence: EvidenceStore, policy: DispositionPolicy, policy_change: dict,
) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    changed_policy = DispositionPolicy.model_validate(policy.model_dump() | policy_change)
    before = state_snapshot(store, proposed.plan.plan_id)
    with pytest.raises(ConflictError):
        InventoryStore(evidence, changed_policy)
    assert state_snapshot(store, proposed.plan.plan_id) == before


def test_separate_connections_competing_for_the_same_components_have_one_winner(
    store: InventoryStore, evidence: EvidenceStore, catalog: Catalog, policy: DispositionPolicy, tmp_path: Path,
) -> None:
    plans = (store.request_plan(scenario_for(evidence)), store.request_plan(scenario_for(evidence)))
    barrier = Barrier(2)

    def reserve(index: int):
        separate = InventoryStore(EvidenceStore(tmp_path / "inventory.sqlite3", catalog), policy)
        barrier.wait(timeout=5)
        try:
            return separate.approve(plans[index].plan.plan_id, approval(plans[index], f"racing-approval-{index}"))
        except ConflictError as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [future.result(timeout=15) for future in (executor.submit(reserve, 0), executor.submit(reserve, 1))]
    winners = [result for result in results if isinstance(result, StoredPlan)]
    assert len(winners) == 1
    assert sum(isinstance(result, ConflictError) for result in results) == 1
    assert {entry.plan_id for entry in store.inventory().items} == {winners[0].plan.plan_id}
    assert sum(event.kind == "approved" for plan in plans for event in store.audit(plan.plan.plan_id)) == 1


def test_cancel_releases_all_reserved_components_and_is_idempotent(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    approved = plan_and_approve(store, evidence)
    command = cancellation(approved)
    cancelled = store.cancel(approved.plan.plan_id, command)
    assert cancelled.state is PlanState.CANCELLED
    assert cancelled.version == approved.version + 1
    assert all(entry.availability is Availability.AVAILABLE for entry in store.inventory().items)
    assert all(entry.plan_id is None for entry in store.inventory().items)
    before = state_snapshot(store, approved.plan.plan_id)
    assert store.cancel(approved.plan.plan_id, command) == cancelled
    assert state_snapshot(store, approved.plan.plan_id) == before


def test_completion_requires_an_approved_reservation(store: InventoryStore, evidence: EvidenceStore) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    action_id = first_rebuild(proposed)
    before = state_snapshot(store, proposed.plan.plan_id)
    with pytest.raises(ConflictError):
        store.complete_action(proposed.plan.plan_id, action_id, completion(proposed, action_id))
    assert state_snapshot(store, proposed.plan.plan_id) == before


@pytest.mark.parametrize("invalid_update", [
    {"confirmed": False}, {"confirmed": 1}, {"evidence_references": ()},
    {"component_ids": ("body-001", "body-001")},
])
def test_completion_command_requires_explicit_confirmation_and_evidence(
    store: InventoryStore, evidence: EvidenceStore, invalid_update: dict,
) -> None:
    approved = plan_and_approve(store, evidence)
    action_id = first_rebuild(approved)
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(ValueError):
        invalid = CompletionCommand.model_validate(completion(approved, action_id).model_dump() | invalid_update)
        store.complete_action(approved.plan.plan_id, action_id, invalid)
    assert state_snapshot(store, approved.plan.plan_id) == before


@pytest.mark.parametrize("component_ids", [("body-001",), ("body-001", "missing-component")])
def test_completion_requires_the_exact_reserved_physical_components(
    store: InventoryStore, evidence: EvidenceStore, component_ids: tuple[str, ...],
) -> None:
    approved = plan_and_approve(store, evidence)
    action_id = first_rebuild(approved)
    invalid = CompletionCommand.model_validate(completion(approved, action_id).model_dump() | {"component_ids": component_ids})
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(ValueError):
        store.complete_action(approved.plan.plan_id, action_id, invalid)
    assert state_snapshot(store, approved.plan.plan_id) == before


def test_completion_consumes_components_once_and_records_completed_kit_lineage(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    approved = plan_and_approve(store, evidence)
    action_id = first_rebuild(approved)
    command = completion(approved, action_id)
    completed = store.complete_action(approved.plan.plan_id, action_id, command)
    assert completed.state is PlanState.COMPLETED
    assert completed.completed_action_ids == (action_id,)
    assert completed.version == approved.version + 1
    snapshot = store.inventory()
    assert all(entry.availability is Availability.CONSUMED for entry in snapshot.items)
    kit, = snapshot.completed_kits
    assert kit.completed_kit_id == command.completed_kit_id
    assert set(kit.component_ids) == {"body-001", "adapter-001"}
    assert kit.plan_id == approved.plan.plan_id
    assert kit.action_id == action_id
    assert kit.configuration_id == "standard-kit"
    assert kit.evidence_references == command.evidence_references
    assert kit.operator_id == command.operator_id
    before = state_snapshot(store, approved.plan.plan_id)
    assert store.complete_action(approved.plan.plan_id, action_id, command) == completed
    assert state_snapshot(store, approved.plan.plan_id) == before
    with pytest.raises(ConflictError):
        store.complete_action(approved.plan.plan_id, action_id, completion(completed, action_id, "second-completion"))
    assert state_snapshot(store, approved.plan.plan_id) == before


def test_evidence_changed_while_reserved_blocks_completion_but_allows_cancellation(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    approved = plan_and_approve(store, evidence)
    action_id = first_rebuild(approved)
    add_new_evidence(evidence)
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(ConflictError):
        store.complete_action(approved.plan.plan_id, action_id, completion(approved, action_id))
    assert state_snapshot(store, approved.plan.plan_id) == before
    cancelled = store.cancel(approved.plan.plan_id, cancellation(approved))
    assert cancelled.state is PlanState.CANCELLED
    availability = {entry.item.component.physical_component_id: entry.availability for entry in store.inventory().items}
    assert availability == {"body-001": Availability.HELD, "adapter-001": Availability.AVAILABLE}


def test_partial_completion_prevents_whole_plan_cancellation_without_releasing_remainder(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    add_component(evidence, "body-002", "body")
    add_component(evidence, "adapter-002", "adapter")
    approved = plan_and_approve(store, evidence)
    actions = tuple(action.action_id for action in approved.plan.selected_actions if action.kind is RecoveryActionKind.REBUILD)
    assert len(actions) == 2
    partially_completed = store.complete_action(approved.plan.plan_id, actions[0], completion(approved, actions[0]))
    assert partially_completed.state is PlanState.APPROVED
    assert len(store.inventory().completed_kits) == 1
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(ConflictError):
        store.cancel(approved.plan.plan_id, cancellation(partially_completed))
    assert state_snapshot(store, approved.plan.plan_id) == before
    assert sum(entry.availability is Availability.RESERVED for entry in store.inventory().items) == 2
    with pytest.raises(ConflictError):
        store.complete_action(
            approved.plan.plan_id, actions[1],
            completion(partially_completed, actions[1], "duplicate-kit-completion", "completed-kit-001"),
        )
    assert state_snapshot(store, approved.plan.plan_id) == before
    completed = store.complete_action(
        approved.plan.plan_id, actions[1],
        completion(partially_completed, actions[1], "complete-002", "completed-kit-002"),
    )
    assert completed.state is PlanState.COMPLETED
    assert len(store.inventory().completed_kits) == 2
    assert all(entry.availability is Availability.CONSUMED for entry in store.inventory().items)


def test_rebuild_completion_requires_an_output_kit_identifier(store: InventoryStore, evidence: EvidenceStore) -> None:
    approved = plan_and_approve(store, evidence)
    action_id = first_rebuild(approved)
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(ValueError):
        store.complete_action(approved.plan.plan_id, action_id, completion(approved, action_id, completed_kit_id=None))
    assert state_snapshot(store, approved.plan.plan_id) == before


def test_cancelled_plan_cannot_be_approved_or_completed(store: InventoryStore, evidence: EvidenceStore) -> None:
    approved = plan_and_approve(store, evidence)
    cancelled = store.cancel(approved.plan.plan_id, cancellation(approved))
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(ConflictError):
        store.approve(cancelled.plan.plan_id, approval(cancelled, "approve-cancelled"))
    with pytest.raises(ConflictError):
        action_id = first_rebuild(cancelled)
        store.complete_action(cancelled.plan.plan_id, action_id, completion(cancelled, action_id))
    assert state_snapshot(store, approved.plan.plan_id) == before


def test_hold_and_retention_do_not_reserve_components_or_create_completed_kits(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    add_component(evidence, "unknown-adapter", "adapter", verified=False)
    proposed = store.request_plan(scenario_for(evidence, donor_value=1000))
    assert {action.kind for action in proposed.plan.selected_actions} == {RecoveryActionKind.RETAIN, RecoveryActionKind.HOLD}
    approved = store.approve(proposed.plan.plan_id, approval(proposed))
    snapshot = store.inventory()
    assert not snapshot.completed_kits
    assert all(entry.availability in (Availability.AVAILABLE, Availability.HELD) for entry in snapshot.items)
    assert all(entry.plan_id is None and entry.action_id is None for entry in snapshot.items)
    action_id = approved.plan.selected_actions[0].action_id
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(ValueError):
        store.complete_action(approved.plan.plan_id, action_id, completion(approved, action_id))
    assert state_snapshot(store, approved.plan.plan_id) == before


@pytest.mark.parametrize("kind", [RecoveryActionKind.SALVAGE, RecoveryActionKind.LIQUIDATE])
def test_other_consuming_dispositions_never_create_a_fake_completed_kit(
    evidence: EvidenceStore, policy: DispositionPolicy, kind: RecoveryActionKind,
) -> None:
    return_ids = tuple(record.return_id for record in evidence.list_returns())
    allowed = DispositionPolicy.model_validate(policy.model_dump() | {
        "liquidation_allowed_return_ids": return_ids if kind is RecoveryActionKind.LIQUIDATE else (),
        "liquidation_allowed_conditions": (VisibleCondition.ACCEPTABLE,),
        "salvage_allowed_component_types": ("body", "adapter") if kind is RecoveryActionKind.SALVAGE else (),
        "salvage_allowed_conditions": (VisibleCondition.ACCEPTABLE,),
    })
    execution = InventoryStore(evidence, allowed)
    scenario = scenario_for(
        evidence, kit_price=0,
        liquidation_values={return_id: 2000 for return_id in return_ids} if kind is RecoveryActionKind.LIQUIDATE else None,
        salvage_value=500 if kind is RecoveryActionKind.SALVAGE else 0,
    )
    proposed = execution.request_plan(scenario)
    assert {action.kind for action in proposed.plan.selected_actions} == {kind}
    current = execution.approve(proposed.plan.plan_id, approval(proposed))
    for index, action in enumerate(proposed.plan.selected_actions):
        before = state_snapshot(execution, proposed.plan.plan_id)
        with pytest.raises(ValueError):
            execution.complete_action(
                proposed.plan.plan_id, action.action_id,
                completion(current, action.action_id, f"invalid-output-{index}", "fake-kit"),
            )
        assert state_snapshot(execution, proposed.plan.plan_id) == before
        current = execution.complete_action(
            proposed.plan.plan_id, action.action_id,
            completion(current, action.action_id, f"nonkit-completion-{index}", None),
        )
    assert current.state is PlanState.COMPLETED
    assert not execution.inventory().completed_kits
    assert all(entry.availability is Availability.CONSUMED for entry in execution.inventory().items)


@pytest.mark.parametrize("already_approved", [False, True])
def test_changed_whole_return_membership_invalidates_liquidation(
    evidence: EvidenceStore, policy: DispositionPolicy, already_approved: bool,
) -> None:
    return_ids = tuple(record.return_id for record in evidence.list_returns())
    allowed = DispositionPolicy.model_validate(policy.model_dump() | {
        "liquidation_allowed_return_ids": return_ids,
        "liquidation_allowed_conditions": (VisibleCondition.ACCEPTABLE,),
    })
    execution = InventoryStore(evidence, allowed)
    proposed = execution.request_plan(scenario_for(evidence, liquidation_values={return_id: 2000 for return_id in return_ids}))
    current = execution.approve(proposed.plan.plan_id, approval(proposed)) if already_approved else proposed
    action = next(action for action in current.plan.selected_actions if action.source_return_id == "return-body-001")
    add_component(evidence, "new-return-member", "adapter", return_id="return-body-001")
    before = state_snapshot(execution, proposed.plan.plan_id)
    with pytest.raises(ConflictError):
        if already_approved:
            execution.complete_action(
                current.plan.plan_id, action.action_id,
                completion(current, action.action_id, completed_kit_id=None),
            )
        else:
            execution.approve(current.plan.plan_id, approval(current))
    assert state_snapshot(execution, proposed.plan.plan_id) == before


def test_a_completed_component_is_excluded_from_subsequent_planning(store: InventoryStore, evidence: EvidenceStore) -> None:
    approved = plan_and_approve(store, evidence)
    action_id = first_rebuild(approved)
    store.complete_action(approved.plan.plan_id, action_id, completion(approved, action_id))
    empty_scenario = EconomicScenario.model_validate(scenario_for(evidence).model_dump() | {"components": ()})
    next_plan = store.request_plan(empty_scenario)
    assert not next_plan.plan.problem.inventory
    assert not next_plan.plan.selected_actions
    assert all(entry.availability is Availability.CONSUMED for entry in store.inventory().items)


def test_unknown_plan_and_action_identifiers_fail_without_mutation(store: InventoryStore, evidence: EvidenceStore) -> None:
    with pytest.raises(NotFoundError):
        store.get_plan("missing-plan")
    approved = plan_and_approve(store, evidence)
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(NotFoundError):
        store.complete_action(approved.plan.plan_id, "missing-action", completion(approved, first_rebuild(approved)))
    assert state_snapshot(store, approved.plan.plan_id) == before


def test_inventory_and_completed_lineage_survive_reopening(
    store: InventoryStore, evidence: EvidenceStore, catalog: Catalog, policy: DispositionPolicy, tmp_path: Path,
) -> None:
    approved = plan_and_approve(store, evidence)
    action_id = first_rebuild(approved)
    store.complete_action(approved.plan.plan_id, action_id, completion(approved, action_id))
    before = state_snapshot(store, approved.plan.plan_id)
    reopened = InventoryStore(EvidenceStore(tmp_path / "inventory.sqlite3", catalog), policy)
    assert state_snapshot(reopened, approved.plan.plan_id) == before


@pytest.mark.parametrize("sql", [
    "UPDATE inventory_audit SET reason = 'changed' WHERE plan_id = ?",
    "DELETE FROM inventory_audit WHERE plan_id = ?",
])
def test_committed_inventory_audit_is_append_only(
    store: InventoryStore, evidence: EvidenceStore, sql: str,
) -> None:
    approved = plan_and_approve(store, evidence)
    before = state_snapshot(store, approved.plan.plan_id)
    with pytest.raises(ConflictError):
        with evidence.transaction() as connection:
            connection.execute(sql, (approved.plan.plan_id,))
    assert state_snapshot(store, approved.plan.plan_id) == before


@pytest.mark.parametrize("operation", ["approve", "complete"])
def test_failure_after_audit_insertion_rolls_back_all_workflow_mutations(
    store: InventoryStore, evidence: EvidenceStore, operation: str,
) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    current = store.approve(proposed.plan.plan_id, approval(proposed)) if operation == "complete" else proposed
    before = state_snapshot(store, proposed.plan.plan_id)
    audit_kind = "action_completed" if operation == "complete" else "approved"
    with evidence.transaction() as connection:
        connection.execute(
            f"""CREATE TRIGGER injected_inventory_failure AFTER INSERT ON inventory_audit
            WHEN NEW.kind = '{audit_kind}'
            BEGIN SELECT RAISE(FAIL, 'Injected workflow failure after audit insertion'); END"""
        )
    with pytest.raises(ConflictError, match="Injected workflow failure"):
        if operation == "approve":
            store.approve(current.plan.plan_id, approval(current))
        else:
            action_id = first_rebuild(current)
            store.complete_action(current.plan.plan_id, action_id, completion(current, action_id))
    assert state_snapshot(store, proposed.plan.plan_id) == before
    with evidence.transaction() as connection:
        connection.execute("DROP TRIGGER injected_inventory_failure")
    if operation == "approve":
        assert store.approve(current.plan.plan_id, approval(current)).state is PlanState.APPROVED
    else:
        action_id = first_rebuild(current)
        assert store.complete_action(current.plan.plan_id, action_id, completion(current, action_id)).state is PlanState.COMPLETED


def test_changed_catalog_cannot_rebind_inventory_with_existing_plans(
    store: InventoryStore, evidence: EvidenceStore, catalog: Catalog, tmp_path: Path,
) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    changed_catalog = Catalog.model_validate(catalog.model_dump() | {"version": "2"})
    before = state_snapshot(store, proposed.plan.plan_id)
    with pytest.raises(ConflictError):
        EvidenceStore(tmp_path / "inventory.sqlite3", changed_catalog)
    assert state_snapshot(store, proposed.plan.plan_id) == before


def test_stored_proposal_is_immutable_under_ordinary_database_writes(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    before = state_snapshot(store, proposed.plan.plan_id)
    with pytest.raises(ConflictError):
        with evidence.transaction() as connection:
            connection.execute(
                "UPDATE recovery_plans SET proposal_json = '{}' WHERE plan_id = ?", (proposed.plan.plan_id,),
            )
    assert state_snapshot(store, proposed.plan.plan_id) == before


def test_corrupted_stored_input_fingerprint_cannot_authorize_reservation(
    store: InventoryStore, evidence: EvidenceStore,
) -> None:
    proposed = store.request_plan(scenario_for(evidence))
    # Simulate privileged storage corruption in this isolated test database.
    # Ordinary writes are blocked by the immutable-proposal trigger tested above.
    with evidence.transaction() as connection:
        connection.execute("DROP TRIGGER recovery_plans_no_update")
        payload = json.loads(connection.execute(
            "SELECT proposal_json FROM recovery_plans WHERE plan_id = ?", (proposed.plan.plan_id,),
        ).fetchone()[0])
        payload["input_hash"] = "0" * 64
        connection.execute(
            "UPDATE recovery_plans SET proposal_json = ? WHERE plan_id = ?",
            (json.dumps(payload), proposed.plan.plan_id),
        )
    inventory_before, audit_before = store.inventory(), store.audit(proposed.plan.plan_id)
    with pytest.raises(ConflictError, match="fingerprint"):
        store.approve(proposed.plan.plan_id, approval(proposed))
    assert store.inventory() == inventory_before
    assert store.audit(proposed.plan.plan_id) == audit_before
