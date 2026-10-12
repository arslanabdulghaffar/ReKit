"""FastAPI composition root."""

from fastapi import FastAPI

from rekit.api.health import router as health_router


def create_app() -> FastAPI:
    """Build the HTTP application without loading models or opening a database."""
    app = FastAPI(title="ReKit API")
    app.include_router(health_router)
    return app


app = create_app()
