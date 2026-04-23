from pydantic import BaseModel


class DiagnosticsSummaryResponse(BaseModel):
    providers_total: int
    providers_enabled: int
    tasks_total: int
    tasks_running: int
    tasks_failed: int
    projects_total: int
    projects_failed: int
    projects_succeeded: int
    files_total: int
    files_size_bytes: int
