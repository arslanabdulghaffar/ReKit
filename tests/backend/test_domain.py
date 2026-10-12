"""Evidence and inventory invariants independent of models, storage, and HTTP."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from rekit.catalog.models import Catalog, ComponentIdentity, VisibleCondition
from rekit.evidence.models import (
    AssertionSource,
    CurrentEvidence,
    IdentityProposal,
    Observation,
    OperatorVerification,
    PhysicalComponent,
    ReturnBatch,
    ReturnRecord,
    VerificationState,
    validate_intake,
)
from rekit.inventory.models import (
    InventoryEligibility,
    InventoryItem,
    validate_inventory,
)


RECORDED_AT = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
PHYSICAL_ID = "physical-001"
RETURN_ID = "return-001"
BATCH_ID = "batch-001"


@pytest.fixture
def catalog() -> Catalog:
    fixture = Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json"
    return Catalog.model_validate_json(fixture.read_text(encoding="utf-8"))


@pytest.fixture
def component() -> PhysicalComponent:
    return PhysicalComponent(
        physical_component_id=PHYSICAL_ID,
        source_return_id=RETURN_ID,
        registered_at=RECORDED_AT,
    )


@pytest.fixture
def identity() -> ComponentIdentity:
    return ComponentIdentity(component_type_id="adapter", revision="A")


@pytest.fixture
def batch() -> ReturnBatch:
    return ReturnBatch(batch_id=BATCH_ID, received_at=RECORDED_AT)


@pytest.fixture
def returned() -> ReturnRecord:
    return ReturnRecord(
        return_id=RETURN_ID,
        batch_id=BATCH_ID,
        product_family_id="demo-kit",
        declared_configuration_id="standard-kit",
        received_at=RECORDED_AT,
    )


def observation(observation_id: str = "observation-001") -> Observation:
    return Observation(
        observation_id=observation_id,
        physical_component_id=PHYSICAL_ID,
        source_return_id=RETURN_ID,
        captured_at=RECORDED_AT,
        evidence_reference=f"synthetic://evidence/{observation_id}",
        source=AssertionSource.MODEL,
        source_reference="synthetic-model-run-001",
    )


def operator_verification(
    identity: ComponentIdentity,
    condition: VisibleCondition = VisibleCondition.ACCEPTABLE,
    physical_id: str = PHYSICAL_ID,
) -> OperatorVerification:
    return OperatorVerification(
        verification_id="verification-001",
        physical_component_id=physical_id,
        identity=identity,
        operator_id="operator-001",
        verified_at=RECORDED_AT,
        evidence_observation_ids=("observation-001",),
        visible_condition=condition,
        reason="Operator read the part marking and inspected visible condition.",
    )


def verified_evidence(verification: OperatorVerification) -> CurrentEvidence:
    return CurrentEvidence(
        physical_component_id=verification.physical_component_id,
        state=VerificationState.VERIFIED,
        verification=verification,
    )


def test_missing_physical_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PhysicalComponent(
            source_return_id=RETURN_ID,
            registered_at=RECORDED_AT,
        )


@pytest.mark.parametrize(
    "invalid_id", ["", " ", " physical-001", "physical-001 ", 42, True, "x" * 129]
)
def test_physical_identifier_is_strict_and_unambiguous(invalid_id: object) -> None:
    with pytest.raises(ValidationError):
        PhysicalComponent(
            physical_component_id=invalid_id,
            source_return_id=RETURN_ID,
            registered_at=RECORDED_AT,
        )


def test_physical_identity_is_immutable(component: PhysicalComponent) -> None:
    with pytest.raises(ValidationError):
        component.physical_component_id = "physical-replacement"


def test_extra_inventory_claim_cannot_be_smuggled_into_observation() -> None:
    payload = observation().model_dump()
    payload["eligible"] = True
    with pytest.raises(ValidationError):
        Observation.model_validate(payload)


def test_unresolved_item_defaults_to_held(component: PhysicalComponent) -> None:
    item = InventoryItem(
        component=component,
        evidence=CurrentEvidence(physical_component_id=PHYSICAL_ID),
    )
    assert item.evidence.state is VerificationState.UNRESOLVED
    assert item.eligibility is InventoryEligibility.HELD


def test_unresolved_item_cannot_be_marked_eligible(component: PhysicalComponent) -> None:
    with pytest.raises(ValidationError):
        InventoryItem(
            component=component,
            evidence=CurrentEvidence(physical_component_id=PHYSICAL_ID),
            eligibility=InventoryEligibility.ELIGIBLE,
        )


def test_inventory_cannot_use_another_physical_components_evidence(
    component: PhysicalComponent,
) -> None:
    with pytest.raises(ValidationError):
        InventoryItem(
            component=component,
            evidence=CurrentEvidence(physical_component_id="physical-other"),
        )


@pytest.mark.parametrize("invalid_version", [0, -1, True, 1.0, "1"])
def test_evidence_version_is_a_strict_positive_integer(invalid_version: object) -> None:
    with pytest.raises(ValidationError):
        CurrentEvidence(physical_component_id=PHYSICAL_ID, version=invalid_version)


def test_verified_state_requires_operator_verification() -> None:
    with pytest.raises(ValidationError):
        CurrentEvidence(
            physical_component_id=PHYSICAL_ID,
            state=VerificationState.VERIFIED,
        )


def test_review_required_state_preserves_an_actionable_reason() -> None:
    with pytest.raises(ValidationError):
        CurrentEvidence(
            physical_component_id=PHYSICAL_ID,
            state=VerificationState.REVIEW_REQUIRED,
        )
    evidence = CurrentEvidence(
        physical_component_id=PHYSICAL_ID,
        state=VerificationState.REVIEW_REQUIRED,
        unresolved_reasons=("Revision marking is obscured; capture a close-up.",),
    )
    assert evidence.unresolved_reasons


def test_unknown_identity_proposal_requires_uncertainty_reason() -> None:
    payload = {
        "proposal_id": "proposal-001",
        "physical_component_id": PHYSICAL_ID,
        "observation_id": "observation-001",
        "proposed_identity": None,
        "created_at": RECORDED_AT,
    }
    with pytest.raises(ValidationError):
        IdentityProposal.model_validate(payload)
    proposal = IdentityProposal.model_validate(
        payload | {"uncertainty_reason": "Revision cannot be read in this image."}
    )
    assert proposal.proposed_identity is None


def test_observation_is_not_operator_verification() -> None:
    with pytest.raises(ValidationError):
        CurrentEvidence(
            physical_component_id=PHYSICAL_ID,
            state=VerificationState.VERIFIED,
            verification=observation(),
        )


def test_identity_proposal_cannot_authorize_inventory(
    component: PhysicalComponent, identity: ComponentIdentity,
) -> None:
    proposal = IdentityProposal(
        proposal_id="proposal-001",
        physical_component_id=PHYSICAL_ID,
        observation_id="observation-001",
        proposed_identity=identity,
        created_at=RECORDED_AT,
    )
    # Serializing the model hypothesis does not turn it into a human assertion.
    for candidate in (proposal, proposal.model_dump()):
        with pytest.raises(ValidationError):
            InventoryItem(
                component=component,
                evidence={
                    "physical_component_id": PHYSICAL_ID,
                    "state": VerificationState.VERIFIED,
                    "verification": candidate,
                },
                eligibility=InventoryEligibility.ELIGIBLE,
            )


@pytest.mark.parametrize("condition", [VisibleCondition.ACCEPTABLE, VisibleCondition.DAMAGED])
def test_known_condition_can_be_eligible_for_later_policy_review(
    catalog: Catalog,
    component: PhysicalComponent,
    identity: ComponentIdentity,
    condition: VisibleCondition,
) -> None:
    item = InventoryItem(
        component=component,
        evidence=verified_evidence(operator_verification(identity, condition)),
        eligibility=InventoryEligibility.ELIGIBLE,
    )
    validate_inventory(catalog, (item,))
    assert item.evidence.verification.visible_condition is condition


def test_unknown_condition_does_not_become_eligible(
    component: PhysicalComponent, identity: ComponentIdentity,
) -> None:
    evidence = verified_evidence(operator_verification(identity, VisibleCondition.UNKNOWN))
    assert InventoryItem(component=component, evidence=evidence).eligibility is InventoryEligibility.HELD
    with pytest.raises(ValidationError):
        InventoryItem(
            component=component, evidence=evidence, eligibility=InventoryEligibility.ELIGIBLE,
        )


def test_verified_state_cannot_hide_unresolved_evidence(identity: ComponentIdentity) -> None:
    with pytest.raises(ValidationError):
        CurrentEvidence(
            physical_component_id=PHYSICAL_ID,
            state=VerificationState.VERIFIED,
            verification=operator_verification(identity),
            unresolved_reasons=("A later capture shows a conflicting revision.",),
        )


def test_verification_must_belong_to_the_same_physical_item(identity: ComponentIdentity) -> None:
    with pytest.raises(ValidationError):
        CurrentEvidence(
            physical_component_id=PHYSICAL_ID,
            state=VerificationState.VERIFIED,
            verification=operator_verification(identity, physical_id="physical-other"),
        )


@pytest.mark.parametrize("state", [VerificationState.UNRESOLVED, VerificationState.REVIEW_REQUIRED])
def test_historical_verification_does_not_override_current_uncertainty(
    component: PhysicalComponent, identity: ComponentIdentity, state: VerificationState,
) -> None:
    previous = operator_verification(identity)
    evidence = CurrentEvidence(
        physical_component_id=PHYSICAL_ID,
        version=2,
        state=state,
        verification=previous,
        unresolved_reasons=("New evidence conflicts with the previous identification.",),
    )
    held = InventoryItem(component=component, evidence=evidence)
    assert held.evidence.verification == previous
    assert held.eligibility is InventoryEligibility.HELD
    with pytest.raises(ValidationError):
        InventoryItem(component=component, evidence=evidence, eligibility=InventoryEligibility.ELIGIBLE)


@pytest.mark.parametrize("evidence_ids", [(), ("observation-001", "observation-001")])
def test_operator_verification_needs_distinct_evidence_links(
    identity: ComponentIdentity, evidence_ids: tuple[str, ...],
) -> None:
    payload = operator_verification(identity).model_dump()
    payload["evidence_observation_ids"] = evidence_ids
    with pytest.raises(ValidationError):
        OperatorVerification.model_validate(payload)


@pytest.mark.parametrize("reason", ["", " \n\t"])
def test_operator_verification_requires_a_nonblank_reason(
    identity: ComponentIdentity, reason: str,
) -> None:
    payload = operator_verification(identity).model_dump() | {"reason": reason}
    with pytest.raises(ValidationError):
        OperatorVerification.model_validate(payload)


def test_correction_retains_prior_verification_reference(identity: ComponentIdentity) -> None:
    original = operator_verification(identity)
    corrected = OperatorVerification.model_validate(
        original.model_dump()
        | {
            "verification_id": "verification-002",
            "visible_condition": VisibleCondition.DAMAGED,
            "reason": "Second view exposes a visible crack.",
            "evidence_observation_ids": ("observation-001", "observation-002"),
            "supersedes_verification_id": original.verification_id,
        }
    )
    assert corrected.supersedes_verification_id == original.verification_id
    assert original.visible_condition is VisibleCondition.ACCEPTABLE
    assert corrected.visible_condition is VisibleCondition.DAMAGED


def test_verification_cannot_supersede_itself(identity: ComponentIdentity) -> None:
    verification = operator_verification(identity)
    with pytest.raises(ValidationError):
        OperatorVerification.model_validate(
            verification.model_dump() | {"supersedes_verification_id": verification.verification_id}
        )


def test_multiple_observations_preserve_one_registered_physical_item(
    catalog: Catalog, batch: ReturnBatch, returned: ReturnRecord, component: PhysicalComponent,
) -> None:
    observations = (observation("overview-001"), observation("close-up-001"))
    components = (component,)
    validate_intake(catalog, (batch,), (returned,), components)
    inventory = (
        InventoryItem(component=component, evidence=CurrentEvidence(physical_component_id=PHYSICAL_ID)),
    )
    validate_inventory(catalog, inventory)
    assert {item.physical_component_id for item in observations} == {PHYSICAL_ID}
    assert len({item.observation_id for item in observations}) == 2
    assert len(components) == len(inventory) == 1
    assert inventory[0].eligibility is InventoryEligibility.HELD


@pytest.mark.parametrize("duplicate_collection", ["batch", "return", "component"])
def test_intake_rejects_duplicate_registered_identifiers(
    catalog: Catalog,
    batch: ReturnBatch,
    returned: ReturnRecord,
    component: PhysicalComponent,
    duplicate_collection: str,
) -> None:
    batches = (batch, batch) if duplicate_collection == "batch" else (batch,)
    returns = (returned, returned) if duplicate_collection == "return" else (returned,)
    components = (component, component) if duplicate_collection == "component" else (component,)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_intake(catalog, batches, returns, components)


def test_intake_rejects_unknown_batch(
    catalog: Catalog, returned: ReturnRecord, component: PhysicalComponent,
) -> None:
    with pytest.raises(ValueError, match="batch"):
        validate_intake(catalog, (), (returned,), (component,))


def test_intake_rejects_unknown_source_return(catalog: Catalog, component: PhysicalComponent) -> None:
    with pytest.raises(ValueError, match="source return"):
        validate_intake(catalog, (), (), (component,))


@pytest.mark.parametrize(
    ("field", "unknown_value"),
    [
        ("product_family_id", "unknown-family"),
        ("declared_configuration_id", "unknown-configuration"),
    ],
)
def test_intake_rejects_unsupported_catalog_references(
    catalog: Catalog, batch: ReturnBatch, returned: ReturnRecord, field: str, unknown_value: str,
) -> None:
    invalid_return = ReturnRecord.model_validate(returned.model_dump() | {field: unknown_value})
    with pytest.raises(ValueError):
        validate_intake(catalog, (batch,), (invalid_return,), ())


def test_intake_rejects_configuration_from_a_different_supported_family(
    catalog: Catalog, batch: ReturnBatch, returned: ReturnRecord,
) -> None:
    payload = catalog.model_dump(mode="json")
    payload["families"].append(
        {"family_id": "other-kit", "name": "Other synthetic kit", "required_component_types": ["other-body"]}
    )
    payload["component_types"].append(
        {"component_type_id": "other-body", "family_id": "other-kit", "name": "Other synthetic body"}
    )
    payload["revisions"].append({"component_type_id": "other-body", "revision": "A"})
    extended_catalog = Catalog.model_validate(payload)
    invalid_return = ReturnRecord.model_validate(returned.model_dump() | {"product_family_id": "other-kit"})
    with pytest.raises(ValueError, match="different product family"):
        validate_intake(extended_catalog, (batch,), (invalid_return,), ())


def test_inventory_rejects_the_same_physical_item_twice(
    catalog: Catalog, component: PhysicalComponent,
) -> None:
    item = InventoryItem(component=component, evidence=CurrentEvidence(physical_component_id=PHYSICAL_ID))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_inventory(catalog, [item, item])


@pytest.mark.parametrize(
    "unknown_identity",
    [
        ComponentIdentity(component_type_id="unknown-part", revision="A"),
        ComponentIdentity(component_type_id="adapter", revision="unknown-revision"),
    ],
)
def test_human_assertion_does_not_override_catalog_membership(
    catalog: Catalog, component: PhysicalComponent, unknown_identity: ComponentIdentity,
) -> None:
    item = InventoryItem(
        component=component,
        evidence=verified_evidence(operator_verification(unknown_identity)),
    )
    with pytest.raises(ValueError):
        validate_inventory(catalog, (item,))


@pytest.mark.parametrize(
    ("model", "timestamp_field"),
    [
        (ReturnBatch, "received_at"),
        (ReturnRecord, "received_at"),
        (PhysicalComponent, "registered_at"),
        (Observation, "captured_at"),
        (IdentityProposal, "created_at"),
        (OperatorVerification, "verified_at"),
    ],
)
def test_provenance_timestamps_require_a_timezone(
    batch: ReturnBatch,
    returned: ReturnRecord,
    component: PhysicalComponent,
    identity: ComponentIdentity,
    model: type,
    timestamp_field: str,
) -> None:
    records = {
        ReturnBatch: batch,
        ReturnRecord: returned,
        PhysicalComponent: component,
        Observation: observation(),
        IdentityProposal: IdentityProposal(
            proposal_id="proposal-001",
            physical_component_id=PHYSICAL_ID,
            observation_id="observation-001",
            proposed_identity=identity,
            created_at=RECORDED_AT,
        ),
        OperatorVerification: operator_verification(identity),
    }
    payload = records[model].model_dump() | {timestamp_field: RECORDED_AT.replace(tzinfo=None)}
    with pytest.raises(ValidationError):
        model.model_validate(payload)
