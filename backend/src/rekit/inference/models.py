"""Bounded, unverified model evidence and its immutable execution provenance."""

from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from rekit.catalog.models import CatalogModel, Identifier
from rekit.evidence.models import Version


AssetId = Annotated[str, StringConstraints(strict=True, pattern=r"^asset-[a-f0-9]{32}$")]
Sha256 = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
Revision = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{40}$")]
Text = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=600, pattern=r"\S")]
Detail = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2000, pattern=r"\S")]
ImageIndex = Annotated[int, Field(strict=True, ge=1, le=2)]
ImageIndices = Annotated[tuple[ImageIndex, ...], Field(min_length=1, max_length=2)]
JsonScalar = (
    Annotated[str, StringConstraints(strict=True, max_length=2000)]
    | Annotated[int, Field(strict=True, ge=-(2**63), le=2**63 - 1)]
    | Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-1e18, le=1e18)]
    | Annotated[bool, Field(strict=True)]
    | None
)
ScalarMap = Annotated[dict[Identifier, JsonScalar], Field(max_length=32)]


class InputAsset(CatalogModel):
    asset_id: AssetId
    sha256: Sha256
    observation_id: Identifier


class InferenceConfiguration(CatalogModel):
    provider: Identifier
    model_repository: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=256, pattern=r"^\S(?:.*\S)?$")]
    model_revision: Revision
    processor_revision: Revision
    runtime: Annotated[
        dict[Identifier, Annotated[str, StringConstraints(strict=True, min_length=1, max_length=512, pattern=r"\S")]],
        Field(min_length=1, max_length=32),
    ]
    device: Identifier
    prompt_version: Identifier
    preprocessing: ScalarMap = Field(min_length=1)
    generation: ScalarMap = Field(min_length=1)


class InspectionRequest(CatalogModel):
    request_id: Identifier
    physical_component_id: Identifier
    asset_ids: tuple[AssetId, ...] = Field(min_length=1, max_length=2)
    expected_version: Version

    @model_validator(mode="after")
    def unique_images(self) -> Self:
        if len(set(self.asset_ids)) != len(self.asset_ids):
            raise ValueError("Requested image assets must be unique")
        return self


class InferenceStart(CatalogModel):
    run_id: Identifier
    request_id: Identifier
    actor_id: Identifier
    physical_component_id: Identifier
    source_return_id: Identifier
    inputs: tuple[InputAsset, ...] = Field(min_length=1, max_length=2)
    evidence_version: Version
    configuration: InferenceConfiguration
    started_at: AwareDatetime

    @model_validator(mode="after")
    def unique_provenance(self) -> Self:
        if len({image.asset_id for image in self.inputs}) != len(self.inputs):
            raise ValueError("Inference input asset IDs must be unique")
        if len({image.observation_id for image in self.inputs}) != len(self.inputs):
            raise ValueError("Inference input observation IDs must be unique")
        return self


class VisualObservation(CatalogModel):
    kind: Literal["appearance", "marking", "visible_damage", "missing_information"]
    text: Text
    image_indices: ImageIndices

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        _unique_indices(self.image_indices)
        return self


class IdentityCandidate(CatalogModel):
    """A possible label, never a verified identity or a compatibility decision."""

    component_type_id: Identifier
    revision: Identifier | None = None
    revision_marking: Text | None = None
    reason: Text
    image_indices: ImageIndices

    @model_validator(mode="after")
    def explicit_visible_revision(self) -> Self:
        _unique_indices(self.image_indices)
        if self.revision is not None and self.revision_marking is None:
            raise ValueError("A proposed revision requires a visible revision marking")
        if self.revision is None and self.revision_marking is not None:
            raise ValueError("A revision marking requires an explicit proposed revision")
        return self


class AdditionalView(CatalogModel):
    view: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200, pattern=r"\S")]
    reason: Text
    image_indices: ImageIndices

    @model_validator(mode="after")
    def unique_sources(self) -> Self:
        _unique_indices(self.image_indices)
        return self


class InspectionOutput(CatalogModel):
    observations: tuple[VisualObservation, ...] = Field(default=(), max_length=6)
    candidates: tuple[IdentityCandidate, ...] = Field(default=(), max_length=3)
    uncertainties: tuple[Text, ...] = Field(default=(), max_length=5)
    additional_views: tuple[AdditionalView, ...] = Field(default=(), max_length=3)

    @model_validator(mode="after")
    def explain_ambiguity(self) -> Self:
        identities = [(candidate.component_type_id, candidate.revision) for candidate in self.candidates]
        if len(set(identities)) != len(identities):
            raise ValueError("Identity candidates must be distinct")
        if len(identities) != 1 and not self.uncertainties:
            raise ValueError("Unknown or conflicting identities require an uncertainty explanation")
        return self

    def validate_image_count(self, image_count: int) -> None:
        if type(image_count) is not int or image_count not in (1, 2):
            raise ValueError("An inference output requires one or two actual input images")
        references = (*self.observations, *self.candidates, *self.additional_views)
        if any(index > image_count for item in references for index in item.image_indices):
            raise ValueError("Model output references an image that was not supplied")


class InferenceOutcome(CatalogModel):
    run_id: Identifier
    status: Literal["succeeded", "failed", "unavailable", "timed_out", "invalid_output"]
    completed_at: AwareDatetime
    output: InspectionOutput | None = None
    raw_output: Annotated[str, StringConstraints(strict=True, max_length=32_000)] | None = None
    failure_reason: Detail | None = None
    metrics: ScalarMap = Field(default_factory=dict)
    stale: Annotated[bool, Field(strict=True)] = False
    stale_reason: Detail | None = None
    applied_event_ids: tuple[Identifier, ...] = Field(default=(), max_length=32)
    evidence_version_after: Version

    @model_validator(mode="after")
    def execution_and_applicability(self) -> Self:
        if self.status == "succeeded":
            if self.output is None or self.failure_reason is not None:
                raise ValueError("Successful inference requires validated output and no failure reason")
        elif self.output is not None or self.failure_reason is None or self.applied_event_ids:
            raise ValueError("Failed inference requires a reason, no validated output, and no applied events")
        if self.stale != (self.stale_reason is not None):
            raise ValueError("A stale outcome requires a reason; a current outcome cannot have one")
        if self.stale and self.applied_event_ids:
            raise ValueError("Stale inference output cannot apply evidence events")
        if len(set(self.applied_event_ids)) != len(self.applied_event_ids):
            raise ValueError("Applied evidence event IDs must be unique")
        return self


class InferenceRun(CatalogModel):
    start: InferenceStart
    outcome: InferenceOutcome | None = None

    @model_validator(mode="after")
    def consistent_execution(self) -> Self:
        if self.outcome is not None:
            if self.outcome.run_id != self.start.run_id:
                raise ValueError("Inference outcome belongs to a different run")
            if self.outcome.completed_at < self.start.started_at:
                raise ValueError("Inference completion cannot precede its start")
            if self.outcome.evidence_version_after < self.start.evidence_version:
                raise ValueError("Inference outcome cannot move the evidence version backwards")
            if self.outcome.output is not None:
                self.outcome.output.validate_image_count(len(self.start.inputs))
        return self


def _unique_indices(indices: tuple[int, ...]) -> None:
    if len(set(indices)) != len(indices):
        raise ValueError("Supporting image indices must be unique")
