import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.diagnostics import router as diagnostics_router
from app.api.routes.projects import router as projects_router
from app.api.routes.providers import router as providers_router
from app.api.routes.settings import router as settings_router
from app.api.routes.system import router as system_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.workflows import router as workflows_router
from app.core.app_state import bootstrap_runtime_state
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    state = bootstrap_runtime_state(settings)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(state.log_file, encoding="utf-8"),
        ],
    )

    application = FastAPI(title="Ecommerce Workbench Desktop API", version="0.1.0")
    application.state.runtime = state
    application.state.task_threads = {}

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(system_router, prefix="/api/v1/system", tags=["system"])
    application.include_router(providers_router, prefix="/api/v1/providers", tags=["providers"])
    application.include_router(settings_router, prefix="/api/v1/settings", tags=["settings"])
    application.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"])
    application.include_router(projects_router, prefix="/api/v1/projects", tags=["projects"])
    application.include_router(workflows_router, prefix="/api/v1/workflows", tags=["workflows"])
    application.include_router(
        diagnostics_router, prefix="/api/v1/diagnostics", tags=["diagnostics"]
    )
    return application
