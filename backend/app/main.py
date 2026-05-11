from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.app.api.routes import ApiServices, create_mock_services, router
from backend.app.core.config import settings


def create_app(
    *,
    asset_base_dirs: list[str | Path] | None = None,
    services: ApiServices | None = None,
) -> FastAPI:
    resolved_services = services or create_mock_services(asset_base_dirs=asset_base_dirs)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.services = resolved_services
        yield
        close = getattr(app.state.services, "close", None)
        if close is not None:
            close()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.state.services = resolved_services
    app.include_router(router)

    return app
