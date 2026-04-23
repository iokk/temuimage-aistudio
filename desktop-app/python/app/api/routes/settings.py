import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_db_connection
from app.models.settings import SettingResponse, SettingUpdate
from app.repositories.settings import get_setting, list_settings, upsert_setting

router = APIRouter()


@router.get("", response_model=list[SettingResponse])
def get_settings(connection: sqlite3.Connection = Depends(get_db_connection)):
    return list_settings(connection)


@router.get("/{key}", response_model=SettingResponse)
def get_setting_detail(
    key: str,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    setting = get_setting(connection, key)
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting


@router.put("/{key}", response_model=SettingResponse)
def put_setting(
    key: str,
    payload: SettingUpdate,
    connection: sqlite3.Connection = Depends(get_db_connection),
):
    return upsert_setting(connection, key, payload.value)
