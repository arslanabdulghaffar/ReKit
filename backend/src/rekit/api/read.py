"""Read-only, server-authoritative records for the operator workbench."""

from typing import Annotated

from fastapi import APIRouter, Query

from rekit.api.workflow import InventoryDependency, Viewer
from rekit.catalog.models import Catalog
from rekit.evidence.models import ReturnBatch, ReturnRecord
from rekit.inventory.execution import PlanSummary


router = APIRouter(tags=["workbench"])


@router.get("/catalog", response_model=Catalog)
def get_catalog(actor: Viewer, inventory: InventoryDependency) -> Catalog:
    return inventory.catalog


@router.get("/batches", response_model=tuple[ReturnBatch, ...])
def get_batches(actor: Viewer, inventory: InventoryDependency) -> tuple[ReturnBatch, ...]:
    return inventory.evidence.list_batches()


@router.get("/returns", response_model=tuple[ReturnRecord, ...])
def get_returns(actor: Viewer, inventory: InventoryDependency) -> tuple[ReturnRecord, ...]:
    return inventory.evidence.list_returns()


@router.get("/plans", response_model=tuple[PlanSummary, ...])
def get_plans(
    actor: Viewer, inventory: InventoryDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> tuple[PlanSummary, ...]:
    return inventory.list_plans(limit)
