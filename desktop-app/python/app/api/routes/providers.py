import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_db_connection
from app.models.provider import (
    ProviderCreate,
    ProviderResponse,
    ProviderTestRequest,
    ProviderTestResponse,
    ProviderUpdate,
)
from app.repositories.providers import (
    create_provider,
    delete_provider,
    get_provider,
    list_providers,
    update_provider,
)
from app.services.provider_test import test_provider_connection

router = APIRouter()


@router.get("", response_model=list[ProviderResponse])
def get_providers(connection: sqlite3.Connection = Depends(get_db_connection)):
    return list_providers(connection)


@router.post("", response_model=ProviderResponse)
def post_provider(
    payload: ProviderCreate,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return create_provider(connection, payload)


@router.get("/{provider_id}", response_model=ProviderResponse)
def get_provider_detail(
    provider_id: str,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    provider = get_provider(connection, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.put("/{provider_id}", response_model=ProviderResponse)
def put_provider(
    provider_id: str,
    payload: ProviderUpdate,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    provider = update_provider(connection, provider_id, payload)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.delete("/{provider_id}")
def delete_provider_detail(
    provider_id: str,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    deleted = delete_provider(connection, provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider not found")
    return {"ok": True}


@router.post("/test", response_model=ProviderTestResponse)
def post_provider_test(payload: ProviderTestRequest):
    ok, message = test_provider_connection(
        api_key=payload.api_key,
        title_model=payload.title_model,
        base_url=payload.base_url,
    )
    return {"ok": ok, "message": message}
