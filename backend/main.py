"""ManiMind FastAPI 应用入口。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.contexts import router as contexts_router
from .api.events import router as events_router
from .api.execution import router as execution_router
from .api.projects import router as projects_router
from .api.reviews import router as reviews_router
from .api.tasks import router as tasks_router


def create_app() -> FastAPI:
    app = FastAPI(title="ManiMind API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
    app.include_router(tasks_router, prefix="/api/projects", tags=["tasks"])
    app.include_router(contexts_router, prefix="/api/projects", tags=["contexts"])
    app.include_router(events_router, prefix="/api/projects", tags=["events"])
    app.include_router(execution_router, prefix="/api/projects", tags=["execution"])
    app.include_router(reviews_router, prefix="/api/projects", tags=["reviews"])
    return app


app = create_app()
