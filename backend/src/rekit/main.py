"""FastAPI composition root with explicit, server-owned workflow configuration."""

import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.responses import Response

from rekit.api.health import router as health_router
from rekit.api.read import router as read_router
from rekit.api.assets import router as assets_router
from rekit.api.workflow import router as workflow_router
from rekit.auth import AuthConfig, AuthDirectory
from rekit.catalog.models import Catalog
from rekit.evidence.store import ConflictError, EvidenceStore, NotFoundError
from rekit.evidence.assets import (
    AssetCorruptError, AssetInvalidError, AssetMissingError, AssetTooLargeError,
    AssetUnavailableError, AssetUnsupportedError, ImageAssetStore,
)
from rekit.inventory.store import InventoryStore
from rekit.recovery.models import DispositionPolicy


def create_app(
    inventory: InventoryStore | None = None, auth: AuthConfig | None = None,
    assets: ImageAssetStore | None = None,
) -> FastAPI:
    """Build the HTTP application without loading models or opening a database."""
    app = FastAPI(
        title="ReKit API",
        description=(
            "Local operator-confirmed recovery workflow with verified image storage. "
            "Image identity and condition require human review; visual inference is not implemented. "
            "Economic values are scenario estimates."
        ),
    )
    app.state.inventory = inventory
    app.state.auth = AuthDirectory(auth) if auth is not None else None
    if assets is not None and (inventory is None or assets.evidence.path != inventory.evidence.path):
        raise ValueError("Image and inventory stores must share the same evidence database.")
    app.state.assets = assets

    @app.middleware("http")
    async def private_responses(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path != "/health":
            response.headers["Cache-Control"] = "no-store"
            vary = response.headers.get("Vary", "")
            fields = [field.strip() for field in vary.split(",") if field.strip()]
            if not any(field.lower() == "authorization" for field in fields):
                fields.append("Authorization")
            response.headers["Vary"] = ", ".join(fields)
        return response

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

    asset_errors = {
        AssetMissingError: 410, AssetCorruptError: 409, AssetUnavailableError: 503,
        AssetTooLargeError: 413, AssetUnsupportedError: 415, AssetInvalidError: 422,
    }

    async def asset_error(_request: Request, error: Exception) -> JSONResponse:
        return JSONResponse(status_code=asset_errors[type(error)], content={"detail": str(error)})

    for error_type in asset_errors:
        app.add_exception_handler(error_type, asset_error)

    app.include_router(health_router)
    app.include_router(workflow_router)
    app.include_router(read_router)
    app.include_router(assets_router)
    return app


def create_configured_app() -> FastAPI:
    """Explicit Uvicorn factory; configuration files are trusted server inputs."""
    names = ("REKIT_DATABASE_PATH", "REKIT_CATALOG_PATH", "REKIT_DISPOSITION_POLICY_PATH", "REKIT_AUTH_CONFIG_PATH")
    values = {name: os.environ.get(name, "") for name in names}
    missing = [name for name, value in values.items() if not value.strip()]
    if missing:
        raise RuntimeError(f"Required server configuration is missing: {', '.join(missing)}")
    try:
        auth = AuthConfig.model_validate_json(Path(values["REKIT_AUTH_CONFIG_PATH"]).read_text(encoding="utf-8"))
    except (ValueError, OSError):
        raise RuntimeError("Authentication configuration could not be loaded or is invalid.") from None
    catalog = Catalog.model_validate_json(Path(values["REKIT_CATALOG_PATH"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json(Path(values["REKIT_DISPOSITION_POLICY_PATH"]).read_text(encoding="utf-8"))
    evidence = EvidenceStore(Path(values["REKIT_DATABASE_PATH"]), catalog)
    asset_root = Path(os.environ.get("REKIT_EVIDENCE_DIR") or evidence.path.parent / "evidence")
    return create_app(InventoryStore(evidence, policy), auth=auth, assets=ImageAssetStore(evidence, asset_root))


app = create_app()
