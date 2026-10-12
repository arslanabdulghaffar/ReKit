"""Eligibility contracts; physical registration and observations do not grant stock approval."""

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from rekit.catalog.models import Catalog, VisibleCondition
from rekit.evidence.models import CurrentEvidence, PhysicalComponent, VerificationState


class InventoryEligibility(StrEnum):
    HELD = "held"
    ELIGIBLE = "eligible"


class InventoryItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    component: PhysicalComponent
    evidence: CurrentEvidence
    eligibility: InventoryEligibility = InventoryEligibility.HELD

    @model_validator(mode="after")
    def verified_eligibility(self) -> Self:
        if self.component.physical_component_id != self.evidence.physical_component_id:
            raise ValueError("Inventory and evidence physical identifiers must match")
        if self.eligibility == InventoryEligibility.ELIGIBLE:
            if self.evidence.state != VerificationState.VERIFIED or self.evidence.verification is None:
                raise ValueError("Eligible inventory requires current operator-verified evidence")
            if self.evidence.verification.visible_condition == VisibleCondition.UNKNOWN:
                raise ValueError("Unknown condition cannot become eligible inventory")
        return self


def validate_inventory(catalog: Catalog, items: tuple[InventoryItem, ...] | list[InventoryItem]) -> None:
    """Validate a snapshot; configuration-specific compatibility is a separate check."""
    identifiers = [item.component.physical_component_id for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate physical_component_id in inventory")
    for item in items:
        if item.evidence.verification is not None:
            catalog.validate_identity(item.evidence.verification.identity)
