"""Process liveness only; this endpoint does not report dependency readiness."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """Stable, minimal liveness response."""

    status: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health() -> HealthResponse:
    """Confirm that the API process can serve a request."""
    return HealthResponse()
