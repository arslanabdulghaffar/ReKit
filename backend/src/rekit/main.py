"""FastAPI composition root with explicit, server-owned workflow configuration."""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from rekit.api.health import router as health_router
from rekit.api.workflow import router as workflow_router
from rekit.catalog.models import Catalog
from rekit.evidence.store import ConflictError, EvidenceStore, NotFoundError
from rekit.inventory.store import InventoryStore
from rekit.recovery.models import DispositionPolicy


def create_app(inventory: InventoryStore | None = None) -> FastAPI:
    """Build the HTTP application without loading models or opening a database."""
    app = FastAPI(
        title="ReKit API",
        description=(
            "Local operator-confirmed recovery workflow. Evidence is supplied metadata; "
            "visual inference and automatic image validation are not implemented. "
            "Economic values are scenario estimates."
        ),
    )
    app.state.inventory = inventory

    @app.exception_handler(NotFoundError)
    async def not_found(_request: Request, error: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(error)})

    @app.exception_handler(ConflictError)
    async def conflict(_request: Request, error: ConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(error)})

    @app.exception_handler(ValidationError)
    async def invalid_business_contract(_request: Request, error: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": error.errors(include_url=False, include_context=False, include_input=False)},
        )

    @app.exception_handler(ValueError)
    async def invalid_business_input(_request: Request, error: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    app.include_router(health_router)
    app.include_router(workflow_router)
    return app


def create_configured_app() -> FastAPI:
    """Explicit Uvicorn factory; configuration files are trusted server inputs."""
    names = ("REKIT_DATABASE_PATH", "REKIT_CATALOG_PATH", "REKIT_DISPOSITION_POLICY_PATH")
    values = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in values.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"Required server configuration is missing: {', '.join(missing)}")
    catalog = Catalog.model_validate_json(Path(values["REKIT_CATALOG_PATH"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json(Path(values["REKIT_DISPOSITION_POLICY_PATH"]).read_text(encoding="utf-8"))
    evidence = EvidenceStore(Path(values["REKIT_DATABASE_PATH"]), catalog)
    return create_app(InventoryStore(evidence, policy))


app = create_app()
