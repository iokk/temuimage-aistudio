from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from apps.api.core.auth import Principal, get_current_principal
from apps.api.core.personal_config import get_personal_execution_config
from apps.api.core.personal_config import serialize_personal_execution_config
from apps.api.core.personal_config import update_personal_execution_config


router = APIRouter(prefix="/personal", tags=["personal"])


class PersonalExecutionConfigRequest(BaseModel):
    use_personal_credentials: bool = False
    provider: str = Field(min_length=1, max_length=32)
    relay_api_base: str = Field(default="", max_length=500)
    relay_api_key: str = Field(default="", max_length=500)
    relay_default_image_model: str = Field(default="", max_length=200)
    gemini_api_key: str = Field(default="", max_length=500)


@router.get("/config")
def personal_config(principal: Principal = Depends(get_current_principal)):
    return serialize_personal_execution_config(
        get_personal_execution_config(principal.user_id)
    )


@router.put("/config")
def personal_config_update(
    payload: PersonalExecutionConfigRequest,
    principal: Principal = Depends(get_current_principal),
):
    config = update_personal_execution_config(principal.user_id, payload.model_dump())
    return serialize_personal_execution_config(config)
