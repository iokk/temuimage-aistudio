from pydantic import BaseModel


class ProjectFileResponse(BaseModel):
    id: str
    project_id: str
    file_role: str
    file_name: str
    file_path: str
    mime_type: str
    file_size: int
    width: int
    height: int
    sort_index: int
    created_at: str


class ProjectResponse(BaseModel):
    id: str
    project_type: str
    summary: str
    status: str
    record_state: str
    provider_id: str
    title_language: str
    image_language: str
    artifact_dir: str
    zip_path: str
    cover_file_id: str
    created_at: str
    started_at: str
    completed_at: str
    updated_at: str
    trashed_at: str
    purged_at: str
    files: list[ProjectFileResponse] = []
    title_text: str = ""
