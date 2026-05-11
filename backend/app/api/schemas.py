from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class CreateTaskRequest(BaseModel):
    command: str


class ApprovalDecisionRequest(BaseModel):
    decided_by: str | None = None
    reason: str | None = None


class CandidateSelectionRequest(BaseModel):
    selected_by: str | None = None


class TaskEnvelope(BaseModel):
    task: dict[str, Any]
    approvals: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    upload_batches: list[dict[str, Any]] = []
    upload_items: list[dict[str, Any]] = []


class EventListResponse(BaseModel):
    events: list[dict[str, Any]]
