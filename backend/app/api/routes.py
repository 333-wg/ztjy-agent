from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.app.agents.ad_upload_agent import AdvertisementUploadAgent
from backend.app.agents.device_ad_agent import DeviceAdvertisementAgent
from backend.app.agents.router import RouteKind, TaskRouter
from backend.app.api.schemas import (
    ApprovalDecisionRequest,
    CandidateSelectionRequest,
    CreateTaskRequest,
    EventListResponse,
    HealthResponse,
    TaskEnvelope,
)
from backend.app.browser.mock_admin import MockAdminAdapter
from backend.app.db.repositories import (
    InMemoryApprovalRepository,
    InMemoryAuditRepository,
    InMemoryCandidateRepository,
    InMemoryLocalAssetCandidateRepository,
    InMemoryTaskRepository,
    InMemoryUploadBatchRepository,
    InMemoryUploadItemRepository,
)
from backend.app.workflows.state import (
    AdvertisementRequest,
    AdvertisementType,
    ApprovalStatus,
    ApprovalType,
    TaskStatus,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@dataclass
class ApiServices:
    task_repo: InMemoryTaskRepository
    approval_repo: InMemoryApprovalRepository
    audit_repo: InMemoryAuditRepository
    candidate_repo: InMemoryCandidateRepository
    batch_repo: InMemoryUploadBatchRepository
    item_repo: InMemoryUploadItemRepository
    asset_candidate_repo: InMemoryLocalAssetCandidateRepository
    device_agent: DeviceAdvertisementAgent
    upload_agent: AdvertisementUploadAgent


def create_mock_services(asset_base_dirs: list[str | Path] | None = None) -> ApiServices:
    task_repo = InMemoryTaskRepository()
    approval_repo = InMemoryApprovalRepository()
    audit_repo = InMemoryAuditRepository()
    candidate_repo = InMemoryCandidateRepository()
    batch_repo = InMemoryUploadBatchRepository()
    item_repo = InMemoryUploadItemRepository()
    asset_candidate_repo = InMemoryLocalAssetCandidateRepository()
    browser = MockAdminAdapter.with_default_fixtures()
    return ApiServices(
        task_repo=task_repo,
        approval_repo=approval_repo,
        audit_repo=audit_repo,
        candidate_repo=candidate_repo,
        batch_repo=batch_repo,
        item_repo=item_repo,
        asset_candidate_repo=asset_candidate_repo,
        device_agent=DeviceAdvertisementAgent(
            browser=browser,
            task_repo=task_repo,
            approval_repo=approval_repo,
            candidate_repo=candidate_repo,
            audit_repo=audit_repo,
        ),
        upload_agent=AdvertisementUploadAgent(
            browser=browser,
            asset_base_dirs=asset_base_dirs or [],
            task_repo=task_repo,
            approval_repo=approval_repo,
            candidate_repo=candidate_repo,
            batch_repo=batch_repo,
            item_repo=item_repo,
            asset_candidate_repo=asset_candidate_repo,
            audit_repo=audit_repo,
        ),
    )


@router.post("/tasks", response_model=TaskEnvelope)
def create_task(payload: CreateTaskRequest, request: Request) -> TaskEnvelope:
    services = _services(request)
    route = TaskRouter().route(payload.command)
    if route.kind == RouteKind.DEVICE_AD_BINDING and route.target_device_no:
        result = services.device_agent.prepare_binding(
            original_command=payload.command,
            target_device_no=route.target_device_no,
            requested_ads=_extract_device_ad_requests(payload.command),
        )
        return _task_envelope(services, result.task.id)
    if route.kind in {RouteKind.AD_UPLOAD, RouteKind.MIXED_UPLOAD_THEN_BIND}:
        try:
            result = services.upload_agent.create_upload_plan(payload.command)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if route.kind == RouteKind.MIXED_UPLOAD_THEN_BIND:
            parsed_command = services.task_repo.get_task(result.task.id).parsed_command or {}
            parsed_command["handoff"] = {
                "next_workflow": "device_ad_binding",
                "target_device_no": route.target_device_no,
                "requires_owner_confirmation": True,
            }
            services.task_repo.update_task(result.task.id, parsed_command=parsed_command)
        return _task_envelope(services, result.task.id)
    raise HTTPException(status_code=400, detail=route.clarification_reason or "unsupported command")


@router.get("/tasks/{task_id}", response_model=TaskEnvelope)
def get_task(task_id: str, request: Request) -> TaskEnvelope:
    return _task_envelope(_services(request), task_id)


@router.get("/tasks/{task_id}/events", response_model=EventListResponse)
def get_task_events(task_id: str, request: Request) -> EventListResponse:
    services = _services(request)
    return EventListResponse(events=[event.model_dump(mode="json") for event in services.audit_repo.list_events(task_id)])


@router.post("/tasks/{task_id}/approvals/{approval_id}/approve", response_model=TaskEnvelope)
def approve_task(
    task_id: str,
    approval_id: str,
    payload: ApprovalDecisionRequest,
    request: Request,
) -> TaskEnvelope:
    services = _services(request)
    task = services.task_repo.get_task(task_id)
    approval = services.approval_repo.get_approval(approval_id)
    if approval.subject_type == "task" and approval.approval_type == ApprovalType.SAVE_APPROVAL:
        services.device_agent.approve_and_save(task_id, approval_id, decided_by=payload.decided_by)
    elif approval.subject_type == "upload_batch" and task.status == TaskStatus.AWAITING_UPLOAD_PLAN_CONFIRMATION:
        services.upload_agent.approve_plan_and_start(task_id, approval_id, decided_by=payload.decided_by)
    elif approval.subject_type == "upload_batch" and task.status == TaskStatus.AWAITING_TAG_CREATION_CONFIRMATION:
        services.upload_agent.approve_tag_creation_and_continue(task_id, approval_id, decided_by=payload.decided_by)
    elif approval.subject_type == "upload_item":
        services.upload_agent.approve_item_and_continue(task_id, approval_id, decided_by=payload.decided_by)
        _prepare_mixed_handoff_if_needed(services, task_id)
    else:
        services.approval_repo.record_decision(
            approval_id,
            ApprovalStatus.APPROVED,
            decision_payload={"confirmed": True},
            decided_by=payload.decided_by,
        )
    return _task_envelope(services, task_id)


@router.post("/tasks/{task_id}/approvals/{approval_id}/reject", response_model=TaskEnvelope)
def reject_task(
    task_id: str,
    approval_id: str,
    payload: ApprovalDecisionRequest,
    request: Request,
) -> TaskEnvelope:
    services = _services(request)
    services.approval_repo.record_decision(
        approval_id,
        ApprovalStatus.REJECTED,
        decision_payload={"reason": payload.reason},
        decided_by=payload.decided_by,
    )
    services.task_repo.update_task(task_id, status=TaskStatus.CANCELLED, awaiting_action=None)
    return _task_envelope(services, task_id)


@router.post("/tasks/{task_id}/candidates/{candidate_id}/select", response_model=TaskEnvelope)
def select_candidate(
    task_id: str,
    candidate_id: str,
    payload: CandidateSelectionRequest,
    request: Request,
) -> TaskEnvelope:
    services = _services(request)
    services.candidate_repo.select_candidate(candidate_id, selected_by=payload.selected_by)
    return _task_envelope(services, task_id)


def _services(request: Request) -> ApiServices:
    return request.app.state.services


def _task_envelope(services: ApiServices, task_id: str) -> TaskEnvelope:
    task = services.task_repo.get_task(task_id)
    batches = services.batch_repo.list_batches(task_id)
    upload_items = []
    for batch in batches:
        upload_items.extend(services.item_repo.list_items(batch.id))
    return TaskEnvelope(
        task=task.model_dump(mode="json"),
        approvals=[approval.model_dump(mode="json") for approval in services.approval_repo.list_approvals(task_id)],
        candidates=[candidate.model_dump(mode="json") for candidate in services.candidate_repo.list_candidates(task_id)],
        upload_batches=[batch.model_dump(mode="json") for batch in batches],
        upload_items=[item.model_dump(mode="json") for item in upload_items],
    )


def _prepare_mixed_handoff_if_needed(services: ApiServices, task_id: str) -> None:
    task = services.task_repo.get_task(task_id)
    handoff = (task.parsed_command or {}).get("handoff")
    if task.status != TaskStatus.SUCCEEDED or not isinstance(handoff, dict):
        return
    if handoff.get("next_workflow") != "device_ad_binding":
        return
    existing = [
        approval
        for approval in services.approval_repo.list_approvals(task_id)
        if approval.subject_type == "task"
        and approval.approval_type == ApprovalType.COMMAND_CONFIRMATION
        and approval.requested_payload.get("handoff") == handoff
    ]
    if not existing:
        services.approval_repo.create_approval(
            task_id=task_id,
            approval_type=ApprovalType.COMMAND_CONFIRMATION,
            requested_payload={"handoff": handoff},
            subject_type="task",
            subject_id=task_id,
        )
    services.task_repo.update_task(
        task_id,
        status=TaskStatus.AWAITING_COMMAND_CONFIRMATION,
        awaiting_action="owner_device_binding_handoff_confirmation",
    )


def _extract_device_ad_requests(command: str) -> list[AdvertisementRequest]:
    name = command
    if "添加" in command:
        name = command.split("添加", 1)[1]
    elif "bind" in command.casefold() and "device" in command.casefold():
        match = re.search(r"bind\s+(.+?)\s+(?:to\s+)?device", command, re.IGNORECASE)
        if match:
            name = match.group(1)
    name = name.replace("广告", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="advertisement name is required")
    lowered = name.casefold()
    if "video" in lowered or "视频" in name:
        ad_type = AdvertisementType.VIDEO
    elif "image" in lowered or "图片" in name:
        ad_type = AdvertisementType.IMAGE
    else:
        ad_type = AdvertisementType.UNKNOWN
    return [AdvertisementRequest(name=name, ad_type=ad_type)]
