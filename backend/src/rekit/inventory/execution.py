"""Operator commands and observable states for transactional recovery execution."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from rekit.catalog.models import CatalogModel, Identifier
from rekit.evidence.models import Text, Version
from rekit.inventory.models import InventoryItem
from rekit.recovery.models import RecoveryActionKind, RecoveryPlan


class PlanState(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Availability(StrEnum):
    AVAILABLE = "available"
    HELD = "held"
    RESERVED = "reserved"
    CONSUMED = "consumed"


class ApprovalCommand(CatalogModel):
    operation_id: Identifier
    operator_id: Identifier
    expected_version: Version
    reason: Text


class CancellationCommand(ApprovalCommand):
    pass


class CompletionCommand(ApprovalCommand):
    confirmed: Annotated[bool, Field(strict=True)]
    component_ids: tuple[Identifier, ...] = Field(min_length=1)
    evidence_references: tuple[Text, ...] = Field(min_length=1)
    completed_kit_id: Identifier | None = None

    @model_validator(mode="after")
    def explicit_confirmation(self) -> Self:
        if self.confirmed is not True:
            raise ValueError("Completion requires explicit operator confirmation")
        if len(set(self.component_ids)) != len(self.component_ids):
            raise ValueError("Completion component IDs must be unique")
        if len(set(self.evidence_references)) != len(self.evidence_references):
            raise ValueError("Completion evidence references must be unique")
        return self


class StoredPlan(CatalogModel):
    plan: RecoveryPlan
    version: Version
    state: PlanState
    completed_action_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def completed_actions_match(self) -> Self:
        consuming = {
            action.action_id for action in self.plan.selected_actions
            if action.kind in (RecoveryActionKind.REBUILD, RecoveryActionKind.SALVAGE, RecoveryActionKind.LIQUIDATE)
        }
        completed = set(self.completed_action_ids)
        if len(completed) != len(self.completed_action_ids) or not completed <= consuming:
            raise ValueError("Completed actions must be unique consuming actions from the stored plan")
        if self.state in (PlanState.PROPOSED, PlanState.CANCELLED) and completed:
            raise ValueError("A proposed or cancelled plan cannot contain completed actions")
        if self.state == PlanState.COMPLETED and completed != consuming:
            raise ValueError("A completed plan must have completed every consuming action")
        return self


class CompletedKit(CatalogModel):
    completed_kit_id: Identifier
    plan_id: Identifier
    action_id: Identifier
    configuration_id: Identifier
    component_ids: tuple[Identifier, ...] = Field(min_length=1)
    operator_id: Identifier
    completed_at: AwareDatetime
    evidence_references: tuple[Text, ...] = Field(min_length=1)


class InventoryEntry(CatalogModel):
    item: InventoryItem
    availability: Availability
    plan_id: Identifier | None = None
    action_id: Identifier | None = None

    @model_validator(mode="after")
    def allocation_matches_state(self) -> Self:
        allocated = self.availability in (Availability.RESERVED, Availability.CONSUMED)
        if allocated != (self.plan_id is not None and self.action_id is not None):
            raise ValueError("Reserved or consumed inventory must name its plan and action")
        if not allocated and (self.plan_id is not None or self.action_id is not None):
            raise ValueError("Unallocated inventory cannot name a plan or action")
        return self


class InventorySnapshot(CatalogModel):
    items: tuple[InventoryEntry, ...]
    completed_kits: tuple[CompletedKit, ...]


class AuditRecord(CatalogModel):
    sequence: Annotated[int, Field(strict=True, gt=0)]
    plan_id: Identifier
    operation_id: Identifier
    operator_id: Identifier
    kind: Literal["proposed", "approved", "cancelled", "action_completed"]
    plan_version: Version
    reason: Text
    recorded_at: AwareDatetime
    action_id: Identifier | None = None
