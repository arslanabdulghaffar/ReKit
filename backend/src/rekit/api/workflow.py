"""Operator-confirmed HTTP workflow; supplied evidence is never automatic inference."""

from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import AwareDatetime, Field

from rekit.auth import Actor, ActorKind, Role, authenticated_actor, require_role
from rekit.catalog.compatibility import CompatibilityDecision, check_compatibility
from rekit.catalog.models import CatalogModel, ComponentIdentity, Identifier, VisibleCondition
from rekit.evidence.models import (
    AssertionSource, CurrentEvidence, EvidenceHistory, IdentityProposal, Observation,
    OperatorVerification, PhysicalComponent, ReturnBatch, ReturnRecord,
    Text, UncertaintyFlag, VerificationState, Version,
)
from rekit.inventory.execution import (
    ApprovalCommand, AuditRecord, CancellationCommand, CompletionCommand,
    InventorySnapshot, StoredPlan,
)
from rekit.inventory.store import InventoryStore
from rekit.recovery.models import EconomicScenario, RecoveryActionKind, SolverSettings


router = APIRouter(tags=["operator workflow"])


class ObservationRequest(CatalogModel):
    kind: Literal["observation"]
    payload: Observation


class ProposalRequest(CatalogModel):
    kind: Literal["proposal"]
    payload: IdentityProposal


class UncertaintyRequest(CatalogModel):
    kind: Literal["uncertainty"]
    payload: UncertaintyFlag


EvidenceRequest = Annotated[
    ObservationRequest | ProposalRequest | UncertaintyRequest,
    Body(discriminator="kind"),
]


class VerificationInput(CatalogModel):
    verification_id: Identifier
    physical_component_id: Identifier
    identity: ComponentIdentity
    verified_at: AwareDatetime
    evidence_observation_ids: tuple[Identifier, ...] = Field(min_length=1)
    visible_condition: VisibleCondition
    reason: Text
    supersedes_verification_id: Identifier | None = None


class VerificationRequest(CatalogModel):
    verification: VerificationInput
    expected_version: Version


class ApprovalInput(CatalogModel):
    operation_id: Identifier
    expected_version: Version
    reason: Text


class CancellationInput(ApprovalInput):
    pass


class CompletionInput(ApprovalInput):
    confirmed: Annotated[bool, Field(strict=True)]
    component_ids: tuple[Identifier, ...] = Field(min_length=1)
    evidence_references: tuple[Text, ...] = Field(min_length=1)
    completed_kit_id: Identifier | None = None


class PlanRequest(CatalogModel):
    scenario: EconomicScenario
    settings: SolverSettings = Field(default_factory=SolverSettings)


def configured_inventory(request: Request) -> InventoryStore:
    inventory = request.app.state.inventory
    if inventory is None:
        raise HTTPException(status_code=503, detail="The recovery workflow is not configured.")
    return inventory


InventoryDependency = Annotated[InventoryStore, Depends(configured_inventory)]
AuthenticatedActor = Annotated[Actor, Depends(authenticated_actor)]
Viewer = Annotated[Actor, Depends(require_role(Role.VIEWER))]
IntakeOperator = Annotated[Actor, Depends(require_role(Role.INTAKE))]
Reviewer = Annotated[Actor, Depends(require_role(Role.REVIEWER, human=True))]
Planner = Annotated[Actor, Depends(require_role(Role.PLANNER))]
Approver = Annotated[Actor, Depends(require_role(Role.APPROVER, human=True))]
Executor = Annotated[Actor, Depends(require_role(Role.EXECUTOR, human=True))]


def _same_component(path_id: str, body_id: str) -> None:
    if path_id != body_id:
        raise HTTPException(status_code=422, detail="Path and payload physical component IDs must match.")


def _assert_asset_reference(http: Request, component_id: str, reference: str) -> None:
    if reference.lower().startswith("asset:"):
        if http.app.state.assets is None:
            raise HTTPException(status_code=503, detail="Image evidence storage is not configured.")
        http.app.state.assets.assert_observation_reference(component_id, reference)


def _assert_verification_assets(
    http: Request, inventory: InventoryStore, component_id: str, observation_ids: tuple[str, ...],
) -> None:
    history = inventory.evidence.history(component_id)
    requested = set(observation_ids)
    for event in history.events:
        if event.kind == "observation" and event.event_id in requested:
            _assert_asset_reference(http, component_id, event.payload.evidence_reference)


def _assert_current_assets(http: Request, inventory: InventoryStore, component_id: str) -> None:
    if http.app.state.assets is not None:
        http.app.state.assets.assert_current_assets(component_id)
        return
    verification = inventory.evidence.current(component_id).verification
    if verification is not None:
        _assert_verification_assets(http, inventory, component_id, verification.evidence_observation_ids)


@router.post("/batches", response_model=ReturnBatch, status_code=201)
def register_batch(batch: ReturnBatch, actor: IntakeOperator, inventory: InventoryDependency) -> ReturnBatch:
    return inventory.evidence.register_batch(batch)


@router.post("/returns", response_model=ReturnRecord, status_code=201)
def register_return(record: ReturnRecord, actor: IntakeOperator, inventory: InventoryDependency) -> ReturnRecord:
    return inventory.evidence.register_return(record)


@router.post("/components", response_model=PhysicalComponent, status_code=201)
def register_component(component: PhysicalComponent, actor: IntakeOperator, inventory: InventoryDependency) -> PhysicalComponent:
    """Register one physical item; this does not make the item verified or eligible."""
    return inventory.evidence.register_component(component)


@router.post("/components/{component_id}/evidence", response_model=CurrentEvidence)
def record_evidence(component_id: Identifier, request: EvidenceRequest, http: Request, actor: IntakeOperator, inventory: InventoryDependency) -> CurrentEvidence:
    """Record supplied metadata or hypotheses without running visual inference."""
    _same_component(component_id, request.payload.physical_component_id)
    payload = request.payload
    if isinstance(payload, (Observation, UncertaintyFlag)) and payload.source == AssertionSource.OPERATOR:
        if actor.kind != ActorKind.HUMAN:
            raise HTTPException(status_code=403, detail="Service actors cannot submit operator-source assertions.")
        payload = type(payload).model_validate(payload.model_dump(mode="json") | {"source_reference": actor.actor_id})
    if isinstance(request, ObservationRequest):
        _assert_asset_reference(http, component_id, payload.evidence_reference)
        return inventory.evidence.record_observation(payload)
    if isinstance(request, ProposalRequest):
        return inventory.evidence.record_proposal(payload)
    return inventory.evidence.flag_uncertainty(payload)


@router.post("/components/{component_id}/verification", response_model=CurrentEvidence)
def verify_component(component_id: Identifier, request: VerificationRequest, http: Request, actor: Reviewer, inventory: InventoryDependency) -> CurrentEvidence:
    """Record an explicit operator verification or a versioned identity correction."""
    _same_component(component_id, request.verification.physical_component_id)
    verification = OperatorVerification.model_validate(request.verification.model_dump(mode="json") | {"operator_id": actor.actor_id})
    _assert_verification_assets(http, inventory, component_id, verification.evidence_observation_ids)
    return inventory.evidence.verify(verification, request.expected_version)


@router.get("/components/{component_id}/history", response_model=EvidenceHistory)
def component_history(component_id: Identifier, actor: Viewer, inventory: InventoryDependency) -> EvidenceHistory:
    return inventory.evidence.history(component_id)


@router.get("/components/{component_id}/compatibility", response_model=CompatibilityDecision)
def component_compatibility(
    component_id: Identifier, configuration_id: Identifier, actor: Viewer, inventory: InventoryDependency,
) -> CompatibilityDecision:
    """Validate stored current verification; compatibility does not imply availability."""
    current = inventory.evidence.current(component_id)
    inventory.catalog.configuration(configuration_id)
    if current.state != VerificationState.VERIFIED or current.verification is None:
        return CompatibilityDecision(
            compatible=False,
            reasons=current.unresolved_reasons or ("Component identity requires operator verification.",),
        )
    return check_compatibility(
        inventory.catalog, configuration_id, current.verification.identity,
        current.verification.visible_condition,
    )


@router.post("/plans", response_model=StoredPlan, status_code=201)
def request_plan(request: PlanRequest, actor: Planner, inventory: InventoryDependency) -> StoredPlan:
    """Plan from server inventory and approved policies using explicit scenario estimates."""
    return inventory.request_plan(request.scenario, request.settings, requested_by=actor.actor_id)


@router.get("/plans/{plan_id}", response_model=StoredPlan)
def get_plan(plan_id: Identifier, actor: Viewer, inventory: InventoryDependency) -> StoredPlan:
    return inventory.get_plan(plan_id)


@router.post("/plans/{plan_id}/approve", response_model=StoredPlan)
def approve_plan(plan_id: Identifier, command: ApprovalInput, http: Request, actor: Approver, inventory: InventoryDependency) -> StoredPlan:
    """Human approval and exclusive reservation commit together in one transaction."""
    bound = ApprovalCommand.model_validate(command.model_dump(mode="json") | {"operator_id": actor.actor_id})
    for action in inventory.get_plan(plan_id).plan.selected_actions:
        if action.kind in (RecoveryActionKind.REBUILD, RecoveryActionKind.SALVAGE, RecoveryActionKind.LIQUIDATE):
            for component_id in action.component_ids:
                _assert_current_assets(http, inventory, component_id)
    return inventory.approve(plan_id, bound)


@router.post("/plans/{plan_id}/cancel", response_model=StoredPlan)
def cancel_plan(plan_id: Identifier, command: CancellationInput, actor: Approver, inventory: InventoryDependency) -> StoredPlan:
    bound = CancellationCommand.model_validate(command.model_dump(mode="json") | {"operator_id": actor.actor_id})
    return inventory.cancel(plan_id, bound)


@router.post("/plans/{plan_id}/actions/{action_id}/complete", response_model=StoredPlan)
def complete_action(
    plan_id: Identifier, action_id: Identifier, command: CompletionInput,
    http: Request, actor: Executor, inventory: InventoryDependency,
) -> StoredPlan:
    """Consume reserved identities only after explicit operator completion evidence."""
    bound = CompletionCommand.model_validate(command.model_dump(mode="json") | {"operator_id": actor.actor_id})
    stored = inventory.get_plan(plan_id)
    action = next((item for item in stored.plan.selected_actions if item.action_id == action_id), None)
    if action is not None:
        for component_id in action.component_ids:
            _assert_current_assets(http, inventory, component_id)
        for reference in command.evidence_references:
            if reference.lower().startswith("asset:"):
                if http.app.state.assets is None:
                    raise HTTPException(status_code=503, detail="Image evidence storage is not configured.")
                asset = http.app.state.assets.metadata(reference[6:])
                if asset.physical_component_id not in action.component_ids:
                    raise HTTPException(status_code=409, detail="Completion image belongs to another physical component.")
                _assert_asset_reference(http, asset.physical_component_id, reference)
    return inventory.complete_action(plan_id, action_id, bound)


@router.get("/plans/{plan_id}/audit", response_model=tuple[AuditRecord, ...])
def plan_audit(plan_id: Identifier, actor: Viewer, inventory: InventoryDependency) -> tuple[AuditRecord, ...]:
    return inventory.audit(plan_id)


@router.get("/inventory", response_model=InventorySnapshot)
def get_inventory(actor: Viewer, inventory: InventoryDependency) -> InventorySnapshot:
    return inventory.inventory()


@router.get("/auth/me", response_model=Actor, tags=["authentication"])
def current_actor(actor: AuthenticatedActor) -> Actor:
    """Expose the authenticated identity and roles without credential material."""
    return actor
