from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskStatus(StrEnum):
    DRAFT = "draft"
    AWAITING_COMMAND_CONFIRMATION = "awaiting_command_confirmation"
    AWAITING_LOGIN = "awaiting_login"
    RUNNING = "running"
    AWAITING_CANDIDATE_SELECTION = "awaiting_candidate_selection"
    AWAITING_SAVE_APPROVAL = "awaiting_save_approval"
    AWAITING_CORRECTION_DECISION = "awaiting_correction_decision"
    AWAITING_UPLOAD_PLAN_CONFIRMATION = "awaiting_upload_plan_confirmation"
    AWAITING_COMPANY_SELECTION = "awaiting_company_selection"
    AWAITING_TAG_SELECTION = "awaiting_tag_selection"
    AWAITING_TAG_CREATION_CONFIRMATION = "awaiting_tag_creation_confirmation"
    AWAITING_ASSET_SELECTION = "awaiting_asset_selection"
    UPLOADING_ASSET = "uploading_asset"
    AWAITING_ITEM_SAVE_APPROVAL = "awaiting_item_save_approval"
    SAVING = "saving"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalType(StrEnum):
    COMMAND_CONFIRMATION = "command_confirmation"
    LOGIN_COMPLETE = "login_complete"
    CANDIDATE_SELECTION = "candidate_selection"
    SAVE_APPROVAL = "save_approval"
    UPLOAD_PLAN_CONFIRMATION = "upload_plan_confirmation"
    TAG_CREATION_CONFIRMATION = "tag_creation_confirmation"
    ITEM_SAVE_APPROVAL = "item_save_approval"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AdvertisementType(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    UNKNOWN = "unknown"


class UploadItemStatus(StrEnum):
    PENDING = "pending"
    ASSET_CANDIDATES_FOUND = "asset_candidates_found"
    AWAITING_ASSET_SELECTION = "awaiting_asset_selection"
    READY_TO_UPLOAD = "ready_to_upload"
    UPLOADING = "uploading"
    AWAITING_ITEM_SAVE_APPROVAL = "awaiting_item_save_approval"
    SAVED = "saved"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class AdvertisementRequest(BaseModel):
    name: str
    ad_type: AdvertisementType = AdvertisementType.UNKNOWN
    category: str | None = None
    notes: str | None = None


class MatchedAdvertisement(BaseModel):
    name: str
    ad_type: AdvertisementType = AdvertisementType.UNKNOWN
    external_ref: str | None = None
    category: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceMatch(BaseModel):
    device_no: str
    external_ref: str | None = None
    display_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTask(BaseModel):
    id: str
    original_command: str
    agent_key: str
    workflow_key: str
    status: TaskStatus = TaskStatus.DRAFT
    current_step: str | None = None
    awaiting_action: str | None = None
    parsed_command: dict[str, Any] | None = None
    target_device_no: str | None = None
    requested_ads: list[AdvertisementRequest] = Field(default_factory=list)
    matched_device: DeviceMatch | None = None
    baseline_ads: list[MatchedAdvertisement] = Field(default_factory=list)
    task_added_ads: list[MatchedAdvertisement] = Field(default_factory=list)
    matched_ads: list[MatchedAdvertisement] = Field(default_factory=list)
    pending_save_report: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class TaskApproval(BaseModel):
    id: str
    task_id: str
    approval_type: ApprovalType
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_payload: dict[str, Any] = Field(default_factory=dict)
    decision_payload: dict[str, Any] | None = None
    requested_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None
    decided_by: str | None = None
    expires_at: datetime | None = None


class AuditEvent(BaseModel):
    id: str
    task_id: str
    event_type: str
    summary: str
    actor_type: str = "agent"
    agent_key: str | None = None
    step_name: str | None = None
    severity: str = "info"
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class TaskCandidate(BaseModel):
    id: str
    task_id: str
    candidate_type: str
    display_name: str
    external_ref: str | None = None
    ad_type: AdvertisementType | None = None
    category: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    selection_status: str = "pending"
    created_at: datetime = Field(default_factory=utc_now)
    selected_at: datetime | None = None
    selected_by: str | None = None


class UploadBatch(BaseModel):
    id: str
    task_id: str
    company_request: str
    tag_request: str | None = None
    matched_company: dict[str, Any] | None = None
    matched_tag: dict[str, Any] | None = None
    created_tag: dict[str, Any] | None = None
    status: str = "draft"
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    skipped_items: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class UploadItem(BaseModel):
    id: str
    task_id: str
    batch_id: str
    item_order: int
    requested_name: str
    requested_type: AdvertisementType = AdvertisementType.UNKNOWN
    requested_category: str | None = None
    local_asset_query: str | None = None
    selected_asset_path: str | None = None
    selected_asset_metadata: dict[str, Any] = Field(default_factory=dict)
    form_payload: dict[str, Any] = Field(default_factory=dict)
    preview_payload: dict[str, Any] = Field(default_factory=dict)
    saved_ad: dict[str, Any] | None = None
    status: UploadItemStatus = UploadItemStatus.PENDING
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class LocalAssetCandidate(BaseModel):
    id: str
    task_id: str
    upload_item_id: str
    file_name: str
    local_path_ref: str
    media_type: AdvertisementType = AdvertisementType.UNKNOWN
    metadata: dict[str, Any] = Field(default_factory=dict)
    selection_status: str = "pending"
    created_at: datetime = Field(default_factory=utc_now)
    selected_at: datetime | None = None
    selected_by: str | None = None
