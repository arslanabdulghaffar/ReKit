"""Physical items, observations, and human assertions are distinct contracts."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from rekit.catalog.models import Catalog, ComponentIdentity, Identifier, VisibleCondition

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=2048)]
Version = Annotated[int, Field(strict=True, ge=1)]


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ReturnBatch(_Record):
    batch_id: Identifier
    received_at: AwareDatetime


class ReturnRecord(_Record):
    return_id: Identifier
    batch_id: Identifier
    product_family_id: Identifier
    received_at: AwareDatetime
    declared_configuration_id: Identifier | None = None


class PhysicalComponent(_Record):
    """An intake identity for one physical object, independent of its part label."""

    physical_component_id: Identifier
    source_return_id: Identifier
    registered_at: AwareDatetime


class AssertionSource(StrEnum):
    OPERATOR = "operator"
    MODEL = "model"
    IMPORT = "import"


class Observation(_Record):
    observation_id: Identifier
    physical_component_id: Identifier
    source_return_id: Identifier
    captured_at: AwareDatetime
    evidence_reference: Text
    source: AssertionSource
    source_reference: Text
    visible_marking: Text | None = None
    visible_revision: Text | None = None


class IdentityProposal(_Record):
    """An unverified hypothesis; it cannot serve as an operator verification."""

    proposal_id: Identifier
    physical_component_id: Identifier
    observation_id: Identifier
    proposed_identity: ComponentIdentity | None
    created_at: AwareDatetime
    uncertainty_reason: Text | None = None

    @model_validator(mode="after")
    def explain_unknown(self) -> Self:
        if self.proposed_identity is None and self.uncertainty_reason is None:
            raise ValueError("An unknown identity requires an uncertainty reason")
        return self


class OperatorVerification(_Record):
    """An explicit human assertion, with the evidence and reason it relies on."""

    verification_id: Identifier
    physical_component_id: Identifier
    identity: ComponentIdentity
    operator_id: Identifier
    verified_at: AwareDatetime
    evidence_observation_ids: tuple[Identifier, ...] = Field(min_length=1)
    visible_condition: VisibleCondition
    reason: Text
    supersedes_verification_id: Identifier | None = None

    @model_validator(mode="after")
    def unique_evidence(self) -> Self:
        if len(set(self.evidence_observation_ids)) != len(self.evidence_observation_ids):
            raise ValueError("Verification evidence observation IDs must be unique")
        if self.supersedes_verification_id == self.verification_id:
            raise ValueError("A verification cannot supersede itself")
        return self


class VerificationState(StrEnum):
    UNRESOLVED = "unresolved"
    REVIEW_REQUIRED = "review_required"
    VERIFIED = "verified"


class CurrentEvidence(_Record):
    physical_component_id: Identifier
    version: Version = 1
    state: VerificationState = VerificationState.UNRESOLVED
    verification: OperatorVerification | None = None
    unresolved_reasons: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def consistent_state(self) -> Self:
        if self.verification and self.verification.physical_component_id != self.physical_component_id:
            raise ValueError("Verification belongs to a different physical component")
        if self.state == VerificationState.VERIFIED:
            if self.verification is None or self.unresolved_reasons:
                raise ValueError("Verified evidence requires human verification and no unresolved reasons")
        if self.state == VerificationState.REVIEW_REQUIRED and not self.unresolved_reasons:
            raise ValueError("Review-required evidence must include a reason")
        return self


def validate_intake(
    catalog: Catalog,
    batches: tuple[ReturnBatch, ...] | list[ReturnBatch],
    returns: tuple[ReturnRecord, ...] | list[ReturnRecord],
    components: tuple[PhysicalComponent, ...] | list[PhysicalComponent],
) -> None:
    """Validate identity uniqueness and intake references without making stock eligible."""
    for records, key in (
        (batches, "batch_id"),
        (returns, "return_id"),
        (components, "physical_component_id"),
    ):
        identifiers = [getattr(record, key) for record in records]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError(f"Duplicate {key}")
    batch_ids = {batch.batch_id for batch in batches}
    return_ids = {record.return_id for record in returns}
    family_ids = {family.family_id for family in catalog.families}
    for record in returns:
        if record.batch_id not in batch_ids:
            raise ValueError(f"Unknown return batch: {record.batch_id}")
        if record.product_family_id not in family_ids:
            raise ValueError(f"Unsupported product family: {record.product_family_id}")
        if record.declared_configuration_id is not None:
            configuration = catalog.configuration(record.declared_configuration_id)
            if configuration.family_id != record.product_family_id:
                raise ValueError("Return configuration belongs to a different product family")
    for component in components:
        if component.source_return_id not in return_ids:
            raise ValueError(f"Unknown source return: {component.source_return_id}")
