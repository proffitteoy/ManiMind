"""ManiMind FastAPI 应用入口。"""

from __future__ import annotations

from fastapi import FastAPI

from .api.contexts import router as contexts_router
from .api.projects import router as projects_router
from .api.tasks import router as tasks_router


def create_app() -> FastAPI:
    app = FastAPI(title="ManiMind API", version="0.1.0")
    app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
    app.include_router(tasks_router, prefix="/api/projects", tags=["tasks"])
    app.include_router(contexts_router, prefix="/api/projects", tags=["contexts"])
    return app


app = create_app()
