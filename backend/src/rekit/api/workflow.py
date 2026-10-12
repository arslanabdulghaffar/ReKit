"""Operator-confirmed HTTP workflow; supplied evidence is never automatic inference."""

from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import Field

from rekit.catalog.compatibility import CompatibilityDecision, check_compatibility
from rekit.catalog.models import CatalogModel, Identifier
from rekit.evidence.models import (
    CurrentEvidence, EvidenceHistory, IdentityProposal, Observation,
    OperatorVerification, PhysicalComponent, ReturnBatch, ReturnRecord,
    UncertaintyFlag, VerificationState, Version,
)
from rekit.inventory.execution import (
    ApprovalCommand, AuditRecord, CancellationCommand, CompletionCommand,
    InventorySnapshot, StoredPlan,
)
from rekit.inventory.store import InventoryStore
from rekit.recovery.models import EconomicScenario, SolverSettings


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


class VerificationRequest(CatalogModel):
    verification: OperatorVerification
    expected_version: Version


class PlanRequest(CatalogModel):
    scenario: EconomicScenario
    settings: SolverSettings = Field(default_factory=SolverSettings)


def configured_inventory(request: Request) -> InventoryStore:
    inventory = request.app.state.inventory
    if inventory is None:
        raise HTTPException(status_code=503, detail="The recovery workflow is not configured.")
    return inventory


InventoryDependency = Annotated[InventoryStore, Depends(configured_inventory)]


def _same_component(path_id: str, body_id: str) -> None:
    if path_id != body_id:
        raise HTTPException(status_code=422, detail="Path and payload physical component IDs must match.")


@router.post("/batches", response_model=ReturnBatch, status_code=201)
def register_batch(batch: ReturnBatch, inventory: InventoryDependency) -> ReturnBatch:
    return inventory.evidence.register_batch(batch)


@router.post("/returns", response_model=ReturnRecord, status_code=201)
def register_return(record: ReturnRecord, inventory: InventoryDependency) -> ReturnRecord:
    return inventory.evidence.register_return(record)


@router.post("/components", response_model=PhysicalComponent, status_code=201)
def register_component(component: PhysicalComponent, inventory: InventoryDependency) -> PhysicalComponent:
    """Register one physical item; this does not make the item verified or eligible."""
    return inventory.evidence.register_component(component)


@router.post("/components/{component_id}/evidence", response_model=CurrentEvidence)
def record_evidence(component_id: Identifier, request: EvidenceRequest, inventory: InventoryDependency) -> CurrentEvidence:
    """Record supplied metadata or hypotheses without running visual inference."""
    _same_component(component_id, request.payload.physical_component_id)
    if isinstance(request, ObservationRequest):
        return inventory.evidence.record_observation(request.payload)
    if isinstance(request, ProposalRequest):
        return inventory.evidence.record_proposal(request.payload)
    return inventory.evidence.flag_uncertainty(request.payload)


@router.post("/components/{component_id}/verification", response_model=CurrentEvidence)
def verify_component(component_id: Identifier, request: VerificationRequest, inventory: InventoryDependency) -> CurrentEvidence:
    """Record an explicit operator verification or a versioned identity correction."""
    _same_component(component_id, request.verification.physical_component_id)
    return inventory.evidence.verify(request.verification, request.expected_version)


@router.get("/components/{component_id}/history", response_model=EvidenceHistory)
def component_history(component_id: Identifier, inventory: InventoryDependency) -> EvidenceHistory:
    return inventory.evidence.history(component_id)


@router.get("/components/{component_id}/compatibility", response_model=CompatibilityDecision)
def component_compatibility(
    component_id: Identifier, configuration_id: Identifier, inventory: InventoryDependency,
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
def request_plan(request: PlanRequest, inventory: InventoryDependency) -> StoredPlan:
    """Plan from server inventory and approved policies using explicit scenario estimates."""
    return inventory.request_plan(request.scenario, request.settings)


@router.get("/plans/{plan_id}", response_model=StoredPlan)
def get_plan(plan_id: Identifier, inventory: InventoryDependency) -> StoredPlan:
    return inventory.get_plan(plan_id)


@router.post("/plans/{plan_id}/approve", response_model=StoredPlan)
def approve_plan(plan_id: Identifier, command: ApprovalCommand, inventory: InventoryDependency) -> StoredPlan:
    """Human approval and exclusive reservation commit together in one transaction."""
    return inventory.approve(plan_id, command)


@router.post("/plans/{plan_id}/cancel", response_model=StoredPlan)
def cancel_plan(plan_id: Identifier, command: CancellationCommand, inventory: InventoryDependency) -> StoredPlan:
    return inventory.cancel(plan_id, command)


@router.post("/plans/{plan_id}/actions/{action_id}/complete", response_model=StoredPlan)
def complete_action(
    plan_id: Identifier, action_id: Identifier, command: CompletionCommand,
    inventory: InventoryDependency,
) -> StoredPlan:
    """Consume reserved identities only after explicit operator completion evidence."""
    return inventory.complete_action(plan_id, action_id, command)


@router.get("/plans/{plan_id}/audit", response_model=tuple[AuditRecord, ...])
def plan_audit(plan_id: Identifier, inventory: InventoryDependency) -> tuple[AuditRecord, ...]:
    return inventory.audit(plan_id)


@router.get("/inventory", response_model=InventorySnapshot)
def get_inventory(inventory: InventoryDependency) -> InventorySnapshot:
    return inventory.inventory()
