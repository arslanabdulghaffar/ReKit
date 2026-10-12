"""Transactional, durable evidence history and human verification boundaries."""

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from rekit.catalog.models import Catalog, ComponentIdentity, VisibleCondition
from rekit.evidence.models import (
    AssertionSource,
    IdentityProposal,
    Observation,
    OperatorVerification,
    PhysicalComponent,
    ReturnBatch,
    ReturnRecord,
    UncertaintyFlag,
    VerificationState,
)
from rekit.evidence.store import ConflictError, EvidenceStore, NotFoundError
from rekit.inventory.models import InventoryEligibility


NOW = datetime(2026, 10, 13, 15, tzinfo=timezone.utc)
COMPONENT_ID = "physical-001"
RETURN_ID = "return-001"
BATCH_ID = "batch-001"


@pytest.fixture
def catalog() -> Catalog:
    path = Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json"
    return Catalog.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.fixture
def store(tmp_path: Path, catalog: Catalog) -> EvidenceStore:
    result = EvidenceStore(tmp_path / "evidence.sqlite3", catalog)
    result.register_batch(ReturnBatch(batch_id=BATCH_ID, received_at=NOW))
    result.register_return(
        ReturnRecord(
            return_id=RETURN_ID,
            batch_id=BATCH_ID,
            product_family_id="demo-kit",
            declared_configuration_id="standard-kit",
            received_at=NOW,
        )
    )
    result.register_component(
        PhysicalComponent(
            physical_component_id=COMPONENT_ID,
            source_return_id=RETURN_ID,
            registered_at=NOW,
        )
    )
    return result


def observation(
    event_id: str = "observation-001",
    component_id: str = COMPONENT_ID,
    return_id: str = RETURN_ID,
) -> Observation:
    return Observation(
        observation_id=event_id,
        physical_component_id=component_id,
        source_return_id=return_id,
        captured_at=NOW,
        evidence_reference=f"synthetic://evidence/{event_id}",
        source=AssertionSource.MODEL,
        source_reference="synthetic-inference-run",
    )


def proposal(
    event_id: str = "proposal-001",
    observation_id: str = "observation-001",
    component_id: str = COMPONENT_ID,
    revision: str | None = "A",
) -> IdentityProposal:
    return IdentityProposal(
        proposal_id=event_id,
        physical_component_id=component_id,
        observation_id=observation_id,
        proposed_identity=(
            ComponentIdentity(component_type_id="adapter", revision=revision)
            if revision is not None else None
        ),
        created_at=NOW,
        uncertainty_reason="Marking is not readable." if revision is None else None,
    )


def verification(
    event_id: str = "verification-001",
    component_id: str = COMPONENT_ID,
    observation_ids: tuple[str, ...] = ("observation-001",),
    revision: str = "A",
    condition: VisibleCondition = VisibleCondition.ACCEPTABLE,
    supersedes: str | None = None,
) -> OperatorVerification:
    return OperatorVerification(
        verification_id=event_id,
        physical_component_id=component_id,
        identity=ComponentIdentity(component_type_id="adapter", revision=revision),
        operator_id="operator-001",
        verified_at=NOW,
        evidence_observation_ids=observation_ids,
        visible_condition=condition,
        reason="Operator inspected the visible marking and condition.",
        supersedes_verification_id=supersedes,
    )


def uncertainty(event_id: str = "flag-001") -> UncertaintyFlag:
    return UncertaintyFlag(
        flag_id=event_id,
        physical_component_id=COMPONENT_ID,
        reason="New view is required to resolve the revision marking.",
        source=AssertionSource.OPERATOR,
        source_reference="operator-001",
        created_at=NOW,
    )


def register_other_component(store: EvidenceStore) -> str:
    other_id = "physical-002"
    store.register_component(
        PhysicalComponent(
            physical_component_id=other_id,
            source_return_id=RETURN_ID,
            registered_at=NOW,
        )
    )
    return other_id


def make_verified(store: EvidenceStore) -> OperatorVerification:
    store.record_observation(observation())
    asserted = verification()
    store.verify(asserted, expected_version=store.current(COMPONENT_ID).version)
    return asserted


def test_registered_component_starts_unresolved_and_held(store: EvidenceStore) -> None:
    assert store.current(COMPONENT_ID).version == 1
    assert store.current(COMPONENT_ID).state is VerificationState.UNRESOLVED
    assert store.get_component(COMPONENT_ID).source_return_id == RETURN_ID
    assert store.inventory_items()[0].eligibility is InventoryEligibility.HELD
    assert {item.return_id for item in store.list_returns()} == {RETURN_ID}


def test_multiple_views_append_evidence_without_creating_inventory(store: EvidenceStore) -> None:
    before = store.current(COMPONENT_ID)
    first, second = observation(), observation("observation-close-up")
    store.record_observation(first)
    store.record_observation(second)
    history = store.history(COMPONENT_ID)
    assert history.component.physical_component_id == COMPONENT_ID
    assert history.current.version == before.version + 2
    assert [event.payload for event in history.events] == [first, second]
    assert [event.sequence for event in history.events] == sorted(
        event.sequence for event in history.events
    )
    assert all(event.recorded_at.tzinfo is not None for event in history.events)
    assert len(store.inventory_items()) == 1
    assert store.inventory_items()[0].eligibility is InventoryEligibility.HELD


@pytest.mark.parametrize("event_kind", ["observation", "proposal", "uncertainty", "verification"])
def test_exact_event_retry_is_idempotent(store: EvidenceStore, event_kind: str) -> None:
    if event_kind != "observation":
        store.record_observation(observation())
    if event_kind == "observation":
        command = lambda: store.record_observation(observation())
    elif event_kind == "proposal":
        command = lambda: store.record_proposal(proposal())
    elif event_kind == "uncertainty":
        command = lambda: store.flag_uncertainty(uncertainty())
    else:
        expected_version = store.current(COMPONENT_ID).version
        command = lambda: store.verify(verification(), expected_version=expected_version)
    command()
    before_retry = store.history(COMPONENT_ID)
    command()
    assert store.history(COMPONENT_ID) == before_retry


def test_reused_event_id_with_different_payload_conflicts_atomically(store: EvidenceStore) -> None:
    original = observation()
    store.record_observation(original)
    before = store.history(COMPONENT_ID)
    altered = Observation.model_validate(original.model_dump() | {"visible_revision": "B"})
    with pytest.raises(ConflictError):
        store.record_observation(altered)
    assert store.history(COMPONENT_ID) == before


def test_event_identifiers_are_unique_across_event_types(store: EvidenceStore) -> None:
    store.record_observation(observation("shared-event-id"))
    before = store.history(COMPONENT_ID)
    with pytest.raises(ConflictError):
        store.record_proposal(proposal("shared-event-id", "shared-event-id"))
    assert store.history(COMPONENT_ID) == before


def test_event_identifiers_are_unique_across_components(store: EvidenceStore) -> None:
    other_id = register_other_component(store)
    store.record_observation(observation())
    before = store.history(other_id)
    with pytest.raises(ConflictError):
        store.record_observation(observation(component_id=other_id))
    assert store.history(other_id) == before


@pytest.mark.parametrize("revision", [None, "A", "not-in-catalog"])
def test_model_hypotheses_never_grant_inventory_eligibility(
    store: EvidenceStore, revision: str | None,
) -> None:
    store.record_observation(observation())
    candidate = proposal(revision=revision)
    store.record_proposal(candidate)
    assert store.history(COMPONENT_ID).events[-1].payload == candidate
    assert store.current(COMPONENT_ID).state is VerificationState.UNRESOLVED
    assert store.current(COMPONENT_ID).verification is None
    assert store.inventory_items()[0].eligibility is InventoryEligibility.HELD


def test_conflicting_hypotheses_require_review(store: EvidenceStore) -> None:
    store.record_observation(observation())
    store.record_proposal(proposal())
    store.record_proposal(proposal("proposal-002", revision="B"))
    current = store.current(COMPONENT_ID)
    assert current.state is VerificationState.REVIEW_REQUIRED
    assert current.unresolved_reasons
    assert current.verification is None
    assert store.inventory_items()[0].eligibility is InventoryEligibility.HELD


def test_explicit_uncertainty_survives_a_later_model_proposal(store: EvidenceStore) -> None:
    store.record_observation(observation())
    store.flag_uncertainty(uncertainty())
    store.record_proposal(proposal())
    current = store.current(COMPONENT_ID)
    assert current.state is VerificationState.REVIEW_REQUIRED
    assert uncertainty().reason in current.unresolved_reasons
    assert store.inventory_items()[0].eligibility is InventoryEligibility.HELD


def test_operator_verification_resolves_evidence_and_grants_eligibility(store: EvidenceStore) -> None:
    store.record_observation(observation())
    store.flag_uncertainty(uncertainty())
    before = store.current(COMPONENT_ID)
    asserted = verification()
    current = store.verify(asserted, expected_version=before.version)
    assert current.version == before.version + 1
    assert current.state is VerificationState.VERIFIED
    assert current.verification == asserted
    assert not current.unresolved_reasons
    assert store.inventory_items()[0].eligibility is InventoryEligibility.ELIGIBLE


def test_verified_identity_with_unknown_visible_condition_stays_held(store: EvidenceStore) -> None:
    store.record_observation(observation())
    store.verify(
        verification(condition=VisibleCondition.UNKNOWN),
        expected_version=store.current(COMPONENT_ID).version,
    )
    assert store.current(COMPONENT_ID).state is VerificationState.VERIFIED
    assert store.inventory_items()[0].eligibility is InventoryEligibility.HELD


@pytest.mark.parametrize("event_kind", ["observation", "proposal", "uncertainty"])
def test_new_evidence_holds_stock_and_retains_previous_verification(
    store: EvidenceStore, event_kind: str,
) -> None:
    previous = make_verified(store)
    if event_kind == "observation":
        store.record_observation(observation("observation-new"))
    elif event_kind == "proposal":
        store.record_proposal(proposal())
    else:
        store.flag_uncertainty(uncertainty())
    current = store.current(COMPONENT_ID)
    assert current.state is VerificationState.REVIEW_REQUIRED
    assert current.verification == previous
    assert current.unresolved_reasons
    assert store.inventory_items()[0].eligibility is InventoryEligibility.HELD


def test_stale_operator_verification_cannot_change_history_or_current_state(store: EvidenceStore) -> None:
    store.record_observation(observation())
    stale_version = store.current(COMPONENT_ID).version
    store.record_observation(observation("observation-new"))
    before = store.history(COMPONENT_ID)
    with pytest.raises(ConflictError):
        store.verify(verification(), expected_version=stale_version)
    assert store.history(COMPONENT_ID) == before


def test_retry_of_old_verification_does_not_undo_later_review(store: EvidenceStore) -> None:
    store.record_observation(observation())
    expected_version = store.current(COMPONENT_ID).version
    asserted = verification()
    store.verify(asserted, expected_version=expected_version)
    store.flag_uncertainty(uncertainty())
    before = store.history(COMPONENT_ID)
    retry_result = store.verify(asserted, expected_version=expected_version)
    assert retry_result == before.current
    assert store.history(COMPONENT_ID) == before
    assert retry_result.state is VerificationState.REVIEW_REQUIRED


def test_correction_appends_and_keeps_the_original_verification(store: EvidenceStore) -> None:
    original = make_verified(store)
    correction = verification("verification-002", revision="B", supersedes=original.verification_id)
    # Capture timestamps are provenance; validated event order determines the current assertion.
    correction = OperatorVerification.model_validate(
        correction.model_dump() | {"verified_at": NOW - timedelta(hours=1)}
    )
    current = store.verify(correction, expected_version=store.current(COMPONENT_ID).version)
    assertions = [
        event.payload for event in store.history(COMPONENT_ID).events
        if isinstance(event.payload, OperatorVerification)
    ]
    assert assertions == [original, correction]
    assert current.verification == correction
    assert correction.supersedes_verification_id == original.verification_id


@pytest.mark.parametrize("supersedes", [None, "verification-not-current"])
def test_correction_requires_the_current_verification_reference(
    store: EvidenceStore, supersedes: str | None,
) -> None:
    make_verified(store)
    before = store.history(COMPONENT_ID)
    with pytest.raises(ConflictError):
        store.verify(
            verification("verification-002", supersedes=supersedes),
            expected_version=before.current.version,
        )
    assert store.history(COMPONENT_ID) == before


def test_observation_must_name_the_registered_source_return(store: EvidenceStore) -> None:
    store.register_return(
        ReturnRecord(
            return_id="return-other",
            batch_id=BATCH_ID,
            product_family_id="demo-kit",
            received_at=NOW,
        )
    )
    before = store.history(COMPONENT_ID)
    with pytest.raises(ValueError):
        store.record_observation(observation(return_id="return-other"))
    assert store.history(COMPONENT_ID) == before


@pytest.mark.parametrize("command", ["observation", "proposal", "verification", "uncertainty"])
def test_commands_cannot_create_an_unregistered_physical_component(
    store: EvidenceStore, command: str,
) -> None:
    unknown_id = "physical-not-registered"
    before = store.inventory_items()
    with pytest.raises(NotFoundError):
        if command == "observation":
            store.record_observation(observation(component_id=unknown_id))
        elif command == "proposal":
            store.record_proposal(proposal(component_id=unknown_id))
        elif command == "verification":
            store.verify(verification(component_id=unknown_id), expected_version=1)
        else:
            store.flag_uncertainty(
                UncertaintyFlag.model_validate(uncertainty().model_dump() | {"physical_component_id": unknown_id})
            )
    assert store.inventory_items() == before


@pytest.mark.parametrize("command", ["proposal", "verification"])
def test_assertions_cannot_link_evidence_from_a_different_component(
    store: EvidenceStore, command: str,
) -> None:
    other_id = register_other_component(store)
    store.record_observation(observation(component_id=other_id))
    before = store.history(COMPONENT_ID)
    with pytest.raises(ValueError):
        if command == "proposal":
            store.record_proposal(proposal())
        else:
            store.verify(verification(), expected_version=before.current.version)
    assert store.history(COMPONENT_ID) == before


@pytest.mark.parametrize("command", ["proposal", "verification"])
def test_assertions_require_existing_observation_links(store: EvidenceStore, command: str) -> None:
    before = store.history(COMPONENT_ID)
    with pytest.raises(NotFoundError):
        if command == "proposal":
            store.record_proposal(proposal())
        else:
            store.verify(verification(), expected_version=before.current.version)
    assert store.history(COMPONENT_ID) == before


def test_failed_multi_observation_verification_is_atomic(store: EvidenceStore) -> None:
    store.record_observation(observation())
    before = store.history(COMPONENT_ID)
    with pytest.raises(NotFoundError):
        store.verify(
            verification(observation_ids=("observation-001", "missing-observation")),
            expected_version=before.current.version,
        )
    assert store.history(COMPONENT_ID) == before


def test_operator_cannot_verify_an_unknown_catalog_revision(store: EvidenceStore) -> None:
    store.record_observation(observation())
    before = store.history(COMPONENT_ID)
    with pytest.raises(ValueError):
        store.verify(verification(revision="not-approved"), expected_version=before.current.version)
    assert store.history(COMPONENT_ID) == before


def test_store_revalidates_models_created_with_validation_bypassed(store: EvidenceStore) -> None:
    store.record_observation(observation())
    before = store.history(COMPONENT_ID)
    invalid = verification().model_copy(
        update={"evidence_observation_ids": ("observation-001", "observation-001")}
    )
    with pytest.raises(ValueError):
        store.verify(invalid, expected_version=before.current.version)
    assert store.history(COMPONENT_ID) == before


def test_existing_component_identity_cannot_be_reassigned_to_another_return(store: EvidenceStore) -> None:
    original = store.get_component(COMPONENT_ID)
    assert store.register_component(original) == original
    store.register_return(
        ReturnRecord(
            return_id="return-other", batch_id=BATCH_ID, product_family_id="demo-kit", received_at=NOW,
        )
    )
    with pytest.raises(ConflictError):
        store.register_component(
            PhysicalComponent.model_validate(original.model_dump() | {"source_return_id": "return-other"})
        )
    assert store.get_component(COMPONENT_ID) == original
    assert len(store.inventory_items()) == 1


def test_registration_validates_batch_and_return_references(store: EvidenceStore) -> None:
    with pytest.raises(ValueError):
        store.register_return(
            ReturnRecord(
                return_id="return-orphan", batch_id="missing-batch", product_family_id="demo-kit", received_at=NOW,
            )
        )
    with pytest.raises(ValueError):
        store.register_component(
            PhysicalComponent(
                physical_component_id="physical-orphan", source_return_id="missing-return", registered_at=NOW,
            )
        )
    assert {item.return_id for item in store.list_returns()} == {RETURN_ID}
    assert {item.component.physical_component_id for item in store.inventory_items()} == {COMPONENT_ID}


@pytest.mark.parametrize("operation", ["current", "history", "get_component"])
def test_unknown_component_reads_report_not_found(store: EvidenceStore, operation: str) -> None:
    with pytest.raises(NotFoundError):
        getattr(store, operation)("physical-not-registered")


def test_reopening_store_preserves_typed_history_and_inventory(
    store: EvidenceStore, tmp_path: Path, catalog: Catalog,
) -> None:
    make_verified(store)
    store.record_observation(observation("observation-new"))
    before = store.history(COMPONENT_ID)
    reopened = EvidenceStore(tmp_path / "evidence.sqlite3", catalog)
    assert reopened.history(COMPONENT_ID) == before
    assert reopened.current(COMPONENT_ID) == before.current
    assert reopened.inventory_items() == store.inventory_items()
    assert reopened.list_returns() == store.list_returns()
    assert any(isinstance(event.payload, OperatorVerification) for event in before.events)


def test_two_store_instances_cannot_overwrite_a_stale_verification(
    store: EvidenceStore, tmp_path: Path, catalog: Catalog,
) -> None:
    store.record_observation(observation())
    second = EvidenceStore(tmp_path / "evidence.sqlite3", catalog)
    stale_version = second.current(COMPONENT_ID).version
    store.verify(verification(), expected_version=stale_version)
    before = store.history(COMPONENT_ID)
    with pytest.raises(ConflictError):
        second.verify(verification("verification-from-stale-review"), expected_version=stale_version)
    assert second.history(COMPONENT_ID) == before


@pytest.mark.parametrize("sql", [
    "UPDATE evidence_events SET payload = '{}' WHERE event_id = ?",
    "DELETE FROM evidence_events WHERE event_id = ?",
])
def test_committed_event_rows_cannot_be_updated_or_deleted(store: EvidenceStore, sql: str) -> None:
    store.record_observation(observation())
    before = store.history(COMPONENT_ID)
    with pytest.raises(ConflictError):
        with store.transaction() as connection:
            connection.execute(sql, ("observation-001",))
    assert store.history(COMPONENT_ID) == before


def test_store_transactions_enable_foreign_key_enforcement(store: EvidenceStore) -> None:
    with store.transaction() as connection:
        assert isinstance(connection, sqlite3.Connection)
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_failure_after_event_insert_rolls_back_history_and_derived_state(store: EvidenceStore) -> None:
    before = store.history(COMPONENT_ID)
    with store.transaction() as connection:
        connection.execute(
            """CREATE TRIGGER injected_write_failure AFTER INSERT ON evidence_events
            WHEN NEW.event_id = 'observation-001'
            BEGIN SELECT RAISE(FAIL, 'Injected failure after event insertion'); END"""
        )
    with pytest.raises(ConflictError, match="Injected failure"):
        store.record_observation(observation())
    assert store.history(COMPONENT_ID) == before
    with store.transaction() as connection:
        connection.execute("DROP TRIGGER injected_write_failure")
    store.record_observation(observation())
    assert store.current(COMPONENT_ID).version == before.current.version + 1
    assert len(store.history(COMPONENT_ID).events) == len(before.events) + 1


@pytest.mark.parametrize("path", ["", ":memory:"])
def test_store_requires_an_explicit_durable_database_path(catalog: Catalog, path: str) -> None:
    with pytest.raises(ValueError):
        EvidenceStore(path, catalog)


@pytest.mark.parametrize("changed_field", ["catalog_id", "version", "description"])
def test_database_cannot_be_reopened_against_a_different_catalog_snapshot(
    store: EvidenceStore, tmp_path: Path, catalog: Catalog, changed_field: str,
) -> None:
    changed = Catalog.model_validate(catalog.model_dump() | {changed_field: "changed"})
    with pytest.raises(ValueError):
        EvidenceStore(tmp_path / "evidence.sqlite3", changed)
    assert store.current(COMPONENT_ID).version == 1
