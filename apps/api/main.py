from fastapi import APIRouter, FastAPI

from apps.api.bootstrap_db import bootstrap_database
from apps.api.core.config import get_settings
from apps.api.routers.batch import router as batch_router
from apps.api.routers.jobs import router as jobs_router
from apps.api.routers.personal import router as personal_router
from apps.api.routers.projects import router as projects_router
from apps.api.routers.quick import router as quick_router
from apps.api.routers.system import router as system_router
from apps.api.routers.title import router as title_router
from apps.api.routers.translate import router as translate_router


settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.on_event("startup")
def startup_bootstrap():
    if settings.auto_bootstrap_db:
        bootstrap_database(settings.database_url)


@app.get("/health")
def health():
    return {"status": "ok"}


api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(system_router)
api_v1.include_router(personal_router)
api_v1.include_router(batch_router)
api_v1.include_router(jobs_router)
api_v1.include_router(projects_router)
api_v1.include_router(quick_router)
api_v1.include_router(title_router)
api_v1.include_router(translate_router)

app.include_router(api_v1)
