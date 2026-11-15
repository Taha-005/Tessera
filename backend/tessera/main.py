"""Builds the FastAPI app. Run with: uvicorn tessera.main:create_app --factory"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tessera.api.health import router as health_router
from tessera.config import Settings
from tessera.rules import load_rules, overrides_path_for


def create_app() -> FastAPI:
    # Read settings first: a missing required setting stops startup here, naming the setting.
    settings = Settings()
    # Then the rule configuration: an invalid rule file also stops startup, listing every problem.
    rules = load_rules(overrides_path=overrides_path_for(settings.data_dir))

    app = FastAPI(title="Tessera")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_allowed_origins)
    app.state.rules = rules
    app.include_router(health_router)
    return app
