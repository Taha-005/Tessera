"""Builds the FastAPI app. Run with: uvicorn tessera.main:create_app --factory"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tessera.api.health import router as health_router
from tessera.config import Settings


def create_app() -> FastAPI:
    # Read settings first: a missing required setting stops startup here, naming the setting.
    settings = Settings()

    app = FastAPI(title="Tessera")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_allowed_origins)
    app.include_router(health_router)
    return app
