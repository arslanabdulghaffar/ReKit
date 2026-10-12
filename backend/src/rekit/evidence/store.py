"""SQLite identity registry and append-only evidence history for operator review."""

from contextlib import contextmanager
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from pydantic import BaseModel

from rekit.catalog.models import Catalog, VisibleCondition
from rekit.evidence.models import (
    CurrentEvidence,
    EvidenceEvent,
    EvidenceHistory,
    IdentityProposal,
    Observation,
    OperatorVerification,
    PhysicalComponent,
    ReturnBatch,
    ReturnRecord,
    UncertaintyFlag,
    VerificationState,
)
from rekit.inventory.models import InventoryEligibility, InventoryItem


class NotFoundError(ValueError):
    """A command references an unregistered entity or observation."""


class ConflictError(ValueError):
    """An existing identity, version, or immutable record conflicts with a command."""


def _canonical(record: BaseModel) -> str:
    return json.dumps(record.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS evidence_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS return_batches (batch_id TEXT PRIMARY KEY, payload TEXT NOT NULL)",
    """CREATE TABLE IF NOT EXISTS returns (
        return_id TEXT PRIMARY KEY,
        batch_id TEXT NOT NULL REFERENCES return_batches(batch_id),
        product_family_id TEXT NOT NULL,
        declared_configuration_id TEXT,
        payload TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS physical_components (
        physical_component_id TEXT PRIMARY KEY,
        source_return_id TEXT NOT NULL REFERENCES returns(return_id),
        payload TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS evidence_events (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id TEXT NOT NULL UNIQUE,
        physical_component_id TEXT NOT NULL REFERENCES physical_components(physical_component_id),
        kind TEXT NOT NULL CHECK (kind IN ('observation', 'proposal', 'uncertainty', 'verification')),
        payload TEXT NOT NULL,
        recorded_at TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS evidence_component_history ON evidence_events(physical_component_id, sequence)",
    """CREATE TRIGGER IF NOT EXISTS evidence_events_no_update BEFORE UPDATE ON evidence_events
        BEGIN SELECT RAISE(ABORT, 'Evidence history is append-only'); END""",
    """CREATE TRIGGER IF NOT EXISTS evidence_events_no_delete BEFORE DELETE ON evidence_events
        BEGIN SELECT RAISE(ABORT, 'Evidence history is append-only'); END""",
)


class EvidenceStore:
    """Connections are short-lived; each write and its prechecks share a transaction."""

    def __init__(self, path: str | Path, catalog: Catalog) -> None:
        if str(path) == ":memory:":
            raise ValueError(":memory: is unsupported; use a SQLite file for per-operation connections")
        self.path = Path(path).resolve()
        if self.path.is_dir():
            raise ValueError("Evidence database path must name a file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog = Catalog.model_validate(catalog.model_dump(mode="json", warnings=False))
        with self.transaction() as connection:
            for statement in _SCHEMA:
                connection.execute(statement)
            existing = connection.execute(
                "SELECT value FROM evidence_metadata WHERE key = 'catalog'"
            ).fetchone()
            catalog_json = _canonical(self.catalog)
            if existing is not None and existing["value"] != catalog_json:
                raise ConflictError("Database catalog differs; catalog migration requires explicit revalidation")
            if existing is None:
                connection.execute(
                    "INSERT INTO evidence_metadata(key, value) VALUES ('catalog', ?)", (catalog_json,)
                )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Expose the same file transaction for later inventory use cases."""
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise ConflictError(str(error)) from error
        except sqlite3.OperationalError as error:
            connection.rollback()
            if "locked" in str(error).lower() or "busy" in str(error).lower():
                raise ConflictError("Database is busy; retry the operation") from error
            raise
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("PRAGMA query_only = ON")
            connection.execute("BEGIN")
            yield connection
        finally:
            connection.rollback()
            connection.close()

    @staticmethod
    def _existing_registration(
        connection: sqlite3.Connection, table: str, key: str, identifier: str, payload: str
    ) -> bool:
        # Table and key are private constants supplied only by the methods below.
        row = connection.execute(f"SELECT payload FROM {table} WHERE {key} = ?", (identifier,)).fetchone()
        if row is None:
            return False
        if row["payload"] != payload:
            raise ConflictError(f"Conflicting registration for {key}: {identifier}")
        return True

    def register_batch(self, batch: ReturnBatch) -> ReturnBatch:
        batch = ReturnBatch.model_validate(batch.model_dump(mode="json", warnings=False))
        payload = _canonical(batch)
        with self.transaction() as connection:
            if not self._existing_registration(connection, "return_batches", "batch_id", batch.batch_id, payload):
                connection.execute("INSERT INTO return_batches(batch_id, payload) VALUES (?, ?)", (batch.batch_id, payload))
        return batch

    def register_return(self, record: ReturnRecord) -> ReturnRecord:
        record = ReturnRecord.model_validate(record.model_dump(mode="json", warnings=False))
        payload = _canonical(record)
        with self.transaction() as connection:
            if self._existing_registration(connection, "returns", "return_id", record.return_id, payload):
                return record
            if connection.execute("SELECT 1 FROM return_batches WHERE batch_id = ?", (record.batch_id,)).fetchone() is None:
                raise NotFoundError(f"Unknown return batch: {record.batch_id}")
            if record.product_family_id not in {family.family_id for family in self.catalog.families}:
                raise ValueError(f"Unsupported product family: {record.product_family_id}")
            if record.declared_configuration_id is not None:
                if self.catalog.configuration(record.declared_configuration_id).family_id != record.product_family_id:
                    raise ValueError("Return configuration belongs to a different product family")
            connection.execute(
                "INSERT INTO returns(return_id, batch_id, product_family_id, declared_configuration_id, payload) VALUES (?, ?, ?, ?, ?)",
                (record.return_id, record.batch_id, record.product_family_id, record.declared_configuration_id, payload),
            )
        return record

    def register_component(self, component: PhysicalComponent) -> PhysicalComponent:
        component = PhysicalComponent.model_validate(component.model_dump(mode="json", warnings=False))
        payload = _canonical(component)
        with self.transaction() as connection:
            if self._existing_registration(connection, "physical_components", "physical_component_id", component.physical_component_id, payload):
                return component
            if connection.execute("SELECT 1 FROM returns WHERE return_id = ?", (component.source_return_id,)).fetchone() is None:
                raise NotFoundError(f"Unknown source return: {component.source_return_id}")
            connection.execute(
                "INSERT INTO physical_components(physical_component_id, source_return_id, payload) VALUES (?, ?, ?)",
                (component.physical_component_id, component.source_return_id, payload),
            )
        return component

    @staticmethod
    def _component(connection: sqlite3.Connection, component_id: str) -> PhysicalComponent:
        row = connection.execute(
            "SELECT payload FROM physical_components WHERE physical_component_id = ?", (component_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"Unknown physical component: {component_id}")
        return PhysicalComponent.model_validate_json(row["payload"])

    def get_component(self, component_id: str) -> PhysicalComponent:
        with self._read() as connection:
            return self._component(connection, component_id)

    def list_returns(self) -> tuple[ReturnRecord, ...]:
        with self._read() as connection:
            return tuple(
                ReturnRecord.model_validate_json(row["payload"])
                for row in connection.execute("SELECT payload FROM returns ORDER BY return_id")
            )

    def list_batches(self) -> tuple[ReturnBatch, ...]:
        with self._read() as connection:
            return tuple(
                ReturnBatch.model_validate_json(row["payload"])
                for row in connection.execute("SELECT payload FROM return_batches ORDER BY batch_id")
            )

    @staticmethod
    def _events(connection: sqlite3.Connection, component_id: str) -> tuple[EvidenceEvent, ...]:
        return tuple(
            EvidenceEvent.model_validate({
                "sequence": row["sequence"], "event_id": row["event_id"], "kind": row["kind"],
                "payload": json.loads(row["payload"]), "recorded_at": row["recorded_at"],
            })
            for row in connection.execute(
                "SELECT sequence, event_id, kind, payload, recorded_at FROM evidence_events WHERE physical_component_id = ? ORDER BY sequence",
                (component_id,),
            )
        )

    def _state(self, component_id: str, events: tuple[EvidenceEvent, ...]) -> CurrentEvidence:
        state = VerificationState.UNRESOLVED
        verification = None
        reasons = ["Identity has not been operator verified"]
        proposed_identities = set()
        for event in events:
            payload = event.payload
            if isinstance(payload, OperatorVerification):
                verification = payload
                state = VerificationState.VERIFIED
                reasons = []
                proposed_identities.clear()
            elif isinstance(payload, UncertaintyFlag):
                state = VerificationState.REVIEW_REQUIRED
                reasons.append(payload.reason)
            elif isinstance(payload, Observation):
                if verification is not None:
                    state = VerificationState.REVIEW_REQUIRED
                    reasons.append(f"Observation {payload.observation_id} was added after verification and requires review")
            elif isinstance(payload, IdentityProposal):
                if verification is not None:
                    state = VerificationState.REVIEW_REQUIRED
                    reasons.append(f"Identity proposal {payload.proposal_id} was added after verification and requires review")
                if payload.proposed_identity is not None:
                    proposed_identities.add(payload.proposed_identity)
                    try:
                        self.catalog.validate_identity(payload.proposed_identity)
                    except ValueError as error:
                        reasons.append(str(error))
                else:
                    reasons.append(f"Identity proposal {payload.proposal_id} is unresolved")
                if payload.uncertainty_reason is not None:
                    reasons.append(payload.uncertainty_reason)
                if len(proposed_identities) > 1:
                    state = VerificationState.REVIEW_REQUIRED
                    reasons.append("Conflicting identity proposals require operator review")
        return CurrentEvidence(
            physical_component_id=component_id, version=1 + len(events), state=state,
            verification=verification, unresolved_reasons=tuple(dict.fromkeys(reasons)),
        )

    def _history(self, connection: sqlite3.Connection, component_id: str) -> EvidenceHistory:
        component = self._component(connection, component_id)
        events = self._events(connection, component_id)
        return EvidenceHistory(component=component, current=self._state(component_id, events), events=events)

    def history(self, component_id: str) -> EvidenceHistory:
        with self._read() as connection:
            return self._history(connection, component_id)

    def current(self, component_id: str) -> CurrentEvidence:
        return self.history(component_id).current

    @staticmethod
    def _duplicate_event(connection: sqlite3.Connection, event_id: str, kind: str, payload: BaseModel) -> bool:
        row = connection.execute("SELECT kind, payload FROM evidence_events WHERE event_id = ?", (event_id,)).fetchone()
        if row is None:
            return False
        if row["kind"] != kind or row["payload"] != _canonical(payload):
            raise ConflictError(f"Event ID already belongs to a different assertion: {event_id}")
        return True

    @staticmethod
    def _append(connection: sqlite3.Connection, event_id: str, kind: str, payload: BaseModel) -> None:
        connection.execute(
            "INSERT INTO evidence_events(event_id, physical_component_id, kind, payload, recorded_at) VALUES (?, ?, ?, ?, ?)",
            (event_id, payload.physical_component_id, kind, _canonical(payload), datetime.now(UTC).isoformat()),
        )

    def is_assertion_retry(self, payload: Observation | OperatorVerification) -> bool:
        """Recognize an exact immutable assertion before checking external assets.

        The subsequent write command still validates and rechecks the same event.
        """
        if isinstance(payload, Observation):
            kind, event_id = "observation", payload.observation_id
        else:
            kind, event_id = "verification", payload.verification_id
        with self._read() as connection:
            return self._duplicate_event(connection, event_id, kind, payload)

    @staticmethod
    def _observation(connection: sqlite3.Connection, observation_id: str, component_id: str) -> Observation:
        row = connection.execute("SELECT kind, physical_component_id, payload FROM evidence_events WHERE event_id = ?", (observation_id,)).fetchone()
        if row is None or row["kind"] != "observation":
            raise NotFoundError(f"Unknown observation: {observation_id}")
        if row["physical_component_id"] != component_id:
            raise ConflictError(f"Observation {observation_id} belongs to a different physical component")
        return Observation.model_validate_json(row["payload"])

    def record_observation(self, observation: Observation) -> CurrentEvidence:
        observation = Observation.model_validate(observation.model_dump(mode="json", warnings=False))
        with self.transaction() as connection:
            if self._duplicate_event(connection, observation.observation_id, "observation", observation):
                return self._history(connection, observation.physical_component_id).current
            component = self._component(connection, observation.physical_component_id)
            if observation.source_return_id != component.source_return_id:
                raise ConflictError("Observation source return does not match the physical component")
            self._append(connection, observation.observation_id, "observation", observation)
            return self._history(connection, observation.physical_component_id).current

    def record_proposal(self, proposal: IdentityProposal) -> CurrentEvidence:
        proposal = IdentityProposal.model_validate(proposal.model_dump(mode="json", warnings=False))
        with self.transaction() as connection:
            if not self._duplicate_event(connection, proposal.proposal_id, "proposal", proposal):
                self._component(connection, proposal.physical_component_id)
                self._observation(connection, proposal.observation_id, proposal.physical_component_id)
                self._append(connection, proposal.proposal_id, "proposal", proposal)
            return self._history(connection, proposal.physical_component_id).current

    def flag_uncertainty(self, flag: UncertaintyFlag) -> CurrentEvidence:
        flag = UncertaintyFlag.model_validate(flag.model_dump(mode="json", warnings=False))
        with self.transaction() as connection:
            if not self._duplicate_event(connection, flag.flag_id, "uncertainty", flag):
                self._component(connection, flag.physical_component_id)
                self._append(connection, flag.flag_id, "uncertainty", flag)
            return self._history(connection, flag.physical_component_id).current

    def verify(self, verification: OperatorVerification, expected_version: int) -> CurrentEvidence:
        verification = OperatorVerification.model_validate(verification.model_dump(mode="json", warnings=False))
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("Expected evidence version must be a positive integer")
        with self.transaction() as connection:
            if self._duplicate_event(connection, verification.verification_id, "verification", verification):
                return self._history(connection, verification.physical_component_id).current
            current = self._history(connection, verification.physical_component_id).current
            if current.version != expected_version:
                raise ConflictError(f"Stale evidence version: expected {expected_version}, current {current.version}")
            previous_id = current.verification.verification_id if current.verification is not None else None
            if verification.supersedes_verification_id != previous_id:
                raise ConflictError("Verification must explicitly supersede the latest operator verification")
            self.catalog.validate_identity(verification.identity)
            for observation_id in verification.evidence_observation_ids:
                self._observation(connection, observation_id, verification.physical_component_id)
            self._append(connection, verification.verification_id, "verification", verification)
            return self._history(connection, verification.physical_component_id).current

    def inventory_items(self) -> tuple[InventoryItem, ...]:
        with self._read() as connection:
            items = []
            for row in connection.execute("SELECT physical_component_id FROM physical_components ORDER BY physical_component_id"):
                history = self._history(connection, row["physical_component_id"])
                eligible = (
                    history.current.state == VerificationState.VERIFIED
                    and history.current.verification is not None
                    and history.current.verification.visible_condition != VisibleCondition.UNKNOWN
                )
                items.append(InventoryItem(
                    component=history.component, evidence=history.current,
                    eligibility=InventoryEligibility.ELIGIBLE if eligible else InventoryEligibility.HELD,
                ))
            return tuple(items)
