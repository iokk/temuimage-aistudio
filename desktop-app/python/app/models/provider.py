from pydantic import BaseModel, Field


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1)
    provider_type: str = Field(min_length=1)
    base_url: str = ""
    title_model: str = ""
    vision_model: str = ""
    image_model: str = ""
    enabled: bool = True
    is_default: bool = False
    secret_ref: str = ""


class ProviderUpdate(BaseModel):
    name: str = Field(min_length=1)
    provider_type: str = Field(min_length=1)
    base_url: str = ""
    title_model: str = ""
    vision_model: str = ""
    image_model: str = ""
    enabled: bool = True
    is_default: bool = False
    secret_ref: str = ""


class ProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    base_url: str
    title_model: str
    vision_model: str
    image_model: str
    enabled: bool
    is_default: bool
    secret_ref: str
    created_at: str
    updated_at: str


class ProviderTestRequest(BaseModel):
    api_key: str = Field(min_length=1)
    title_model: str = ""
    base_url: str = ""


class ProviderTestResponse(BaseModel):
    ok: bool
    message: str
