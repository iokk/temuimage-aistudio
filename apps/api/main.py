from fastapi import APIRouter, FastAPI

from apps.api.core.config import get_settings
from apps.api.routers.jobs import router as jobs_router
from apps.api.routers.system import router as system_router


settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.get("/health")
def health():
    return {"status": "ok"}


api_v1 = APIRouter(prefix="/v1")
api_v1.include_router(system_router)
api_v1.include_router(jobs_router)

app.include_router(api_v1)
