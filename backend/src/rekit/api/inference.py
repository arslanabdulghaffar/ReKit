"""Authenticated visual inspection of existing managed images only."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field

from rekit.api.workflow import Viewer
from rekit.auth import Actor, Role, require_role
from rekit.catalog.models import CatalogModel, Identifier
from rekit.evidence.models import CurrentEvidence
from rekit.inference.models import AssetId, InferenceRun, InspectionRequest, InspectionRejection
from rekit.inference.service import InferenceService


router = APIRouter(tags=["visual inspection"])
Reviewer = Annotated[Actor, Depends(require_role(Role.REVIEWER, human=True))]


class AnalyzeImages(CatalogModel):
    request_id: Identifier
    asset_ids: tuple[AssetId, ...] = Field(min_length=1, max_length=2)
    expected_version: int = Field(strict=True, ge=1)


def configured_inference(request: Request) -> InferenceService:
    service = request.app.state.inference
    if service is None:
        raise HTTPException(status_code=503, detail="Visual inference is unavailable; manual inspection remains available.")
    return service


InferenceDependency = Annotated[InferenceService, Depends(configured_inference)]


@router.get("/inference/status")
def inference_status(actor: Viewer, request: Request) -> dict:
    service = request.app.state.inference
    if service is None:
        return {"status": "unavailable", "busy": False, "provider": None,
                "model_repository": None, "model_revision": None, "device": None}
    return service.status()


@router.post("/components/{component_id}/inference", response_model=InferenceRun, status_code=202)
def analyze(component_id: Identifier, body: AnalyzeImages, actor: Reviewer,
            service: InferenceDependency) -> InferenceRun:
    command = InspectionRequest(physical_component_id=component_id, **body.model_dump())
    return service.submit(command, actor)


@router.get("/components/{component_id}/inference", response_model=tuple[InferenceRun, ...])
def component_runs(component_id: Identifier, actor: Viewer, service: InferenceDependency) -> tuple[InferenceRun, ...]:
    return service.store.list_for_component(component_id)


@router.get("/inference/{run_id}", response_model=InferenceRun)
def inference_run(run_id: Identifier, actor: Viewer, service: InferenceDependency) -> InferenceRun:
    return service.store.get(run_id)


@router.post("/inference/{run_id}/reject", response_model=CurrentEvidence)
def reject_inference(run_id: Identifier, body: InspectionRejection, actor: Reviewer,
                     service: InferenceDependency) -> CurrentEvidence:
    return service.store.reject(run_id, body, actor)
