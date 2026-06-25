from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from app.api.cases import router as cases_router
from app.api.environments import router as environments_router
from app.api.projects import router as projects_router
from app.api.runs import router as runs_router
from app.api.versions import router as versions_router
from app.core.config import Settings
from app.core.database import SessionFactory
from app.core.errors import register_error_handlers
from app.execution.job_manager import JobManager


def create_app(
    settings: Settings | None = None,
    job_manager: Any | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        manager = application.state.job_manager
        if manager is not None and hasattr(manager, "start"):
            manager.start()
        yield
        if manager is not None and hasattr(manager, "stop"):
            manager.stop()

    application = FastAPI(
        title=resolved_settings.app_name,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.job_manager = job_manager
    register_error_handlers(application)
    application.include_router(projects_router)
    application.include_router(environments_router)
    application.include_router(cases_router)
    application.include_router(versions_router)
    application.include_router(runs_router)

    @application.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "beehive-interface-backend",
        }

    return application


app = create_app(
    job_manager=JobManager(
        settings=Settings(),
        session_factory=SessionFactory,
    )
)
