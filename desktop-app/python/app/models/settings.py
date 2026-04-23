from typing import Any

from pydantic import BaseModel, Field


class SettingResponse(BaseModel):
    key: str
    value: Any
    updated_at: str


class SettingUpdate(BaseModel):
    value: Any = Field(default=None)
