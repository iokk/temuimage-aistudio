from fastapi import APIRouter, HTTPException, Request

from app.models.workflows import (
    QuickGenerateWorkflowRequest,
    SmartGenerateWorkflowRequest,
    TitleWorkflowRequest,
    TranslationWorkflowRequest,
    WorkflowSubmissionResponse,
)
from app.services.smart_workflow import create_smart_workflow
from app.services.quick_workflow import create_quick_workflow
from app.services.title_workflow import create_title_workflow
from app.services.translation_workflow import create_translation_workflow

router = APIRouter()


@router.post("/title", response_model=WorkflowSubmissionResponse)
def submit_title_workflow(payload: TitleWorkflowRequest, request: Request):
    if not payload.product_info.strip() and not payload.image_paths:
        raise HTTPException(
            status_code=400, detail="Title workflow requires product_info or image_paths."
        )
    return create_title_workflow(
        request.app,
        provider_id=payload.provider_id,
        api_key=payload.api_key,
        product_info=payload.product_info,
        template_prompt=payload.template_prompt,
        title_language=payload.title_language,
        image_paths=payload.image_paths,
    )


@router.post("/translate", response_model=WorkflowSubmissionResponse)
def submit_translation_workflow(
    payload: TranslationWorkflowRequest, request: Request
):
    return create_translation_workflow(
        request.app,
        provider_id=payload.provider_id,
        api_key=payload.api_key,
        image_paths=payload.image_paths,
        image_language=payload.image_language,
        compliance_mode=payload.compliance_mode,
        aspect_ratio=payload.aspect_ratio,
        image_model=payload.image_model,
    )


@router.post("/quick-generate", response_model=WorkflowSubmissionResponse)
def submit_quick_generate_workflow(
    payload: QuickGenerateWorkflowRequest, request: Request
):
    return create_quick_workflow(
        request.app,
        provider_id=payload.provider_id,
        api_key=payload.api_key,
        image_paths=payload.image_paths,
        product_name=payload.product_name,
        product_detail=payload.product_detail,
        output_language=payload.output_language,
        aspect_ratio=payload.aspect_ratio,
        image_model=payload.image_model,
        quick_mode=payload.quick_mode,
        image_count=payload.image_count,
    )


@router.post("/smart-generate", response_model=WorkflowSubmissionResponse)
def submit_smart_generate_workflow(
    payload: SmartGenerateWorkflowRequest, request: Request
):
    return create_smart_workflow(
        request.app,
        provider_id=payload.provider_id,
        api_key=payload.api_key,
        image_paths=payload.image_paths,
        product_name=payload.product_name,
        product_detail=payload.product_detail,
        image_language=payload.image_language,
        aspect_ratio=payload.aspect_ratio,
        image_model=payload.image_model,
        selected_types=payload.selected_types,
    )
