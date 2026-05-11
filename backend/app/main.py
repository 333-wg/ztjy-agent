from fastapi import FastAPI

from backend.app.api.routes import router
from backend.app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(router)
    return app
