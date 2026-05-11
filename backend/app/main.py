from pathlib import Path

from fastapi import FastAPI

from backend.app.api.routes import ApiServices, create_mock_services, router
from backend.app.core.config import settings


def create_app(
    *,
    asset_base_dirs: list[str | Path] | None = None,
    services: ApiServices | None = None,
) -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.state.services = services or create_mock_services(asset_base_dirs=asset_base_dirs)
    app.include_router(router)
    return app
