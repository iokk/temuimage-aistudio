from pydantic import BaseModel, Field


class TitleWorkflowRequest(BaseModel):
    provider_id: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    product_info: str = ""
    template_prompt: str = ""
    title_language: str = "en"
    image_paths: list[str] = []


class WorkflowSubmissionResponse(BaseModel):
    task_id: str
    project_id: str
    status: str


class TranslationWorkflowRequest(BaseModel):
    provider_id: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    image_paths: list[str] = Field(min_length=1)
    image_language: str = "en"
    compliance_mode: str = "strict"
    aspect_ratio: str = "1:1"
    image_model: str = ""


class QuickGenerateWorkflowRequest(BaseModel):
    provider_id: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    image_paths: list[str] = Field(min_length=1)
    product_name: str = Field(min_length=1)
    product_detail: str = ""
    output_language: str = "en"
    aspect_ratio: str = "1:1"
    image_model: str = ""
    quick_mode: str = "hero"
    image_count: int = Field(default=1, ge=1, le=4)


class SmartGenerateWorkflowRequest(BaseModel):
    provider_id: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    image_paths: list[str] = Field(min_length=1)
    product_name: str = Field(min_length=1)
    product_detail: str = ""
    image_language: str = "en"
    aspect_ratio: str = "1:1"
    image_model: str = ""
    selected_types: dict[str, int] = Field(default_factory=dict)
