from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, TypeVar
from uuid import uuid4

from backend.app.workflows.state import (
    AdvertisementType,
    AgentTask,
    ApprovalStatus,
    ApprovalType,
    AuditEvent,
    LocalAssetCandidate,
    TaskApproval,
    TaskCandidate,
    TaskStatus,
    UploadBatch,
    UploadItem,
    UploadItemStatus,
    utc_now,
)


def _new_id() -> str:
    return str(uuid4())


T = TypeVar("T")


def _copy(model: T) -> T:
    return deepcopy(model)


class TaskRepository(Protocol):
    def create_task(self, original_command: str, agent_key: str, workflow_key: str) -> AgentTask: ...

    def get_task(self, task_id: str) -> AgentTask: ...

    def update_task_status(self, task_id: str, status: TaskStatus) -> AgentTask: ...

    def update_task(self, task_id: str, **changes: Any) -> AgentTask: ...


class ApprovalRepository(Protocol):
    def create_approval(
        self,
        task_id: str,
        approval_type: ApprovalType,
        requested_payload: dict[str, Any] | None = None,
        subject_type: str = "task",
        subject_id: str | None = None,
    ) -> TaskApproval: ...

    def get_approval(self, approval_id: str) -> TaskApproval: ...

    def record_decision(
        self,
        approval_id: str,
        status: ApprovalStatus,
        decision_payload: dict[str, Any] | None = None,
        decided_by: str | None = None,
    ) -> TaskApproval: ...


class AuditRepository(Protocol):
    def record_event(self, task_id: str, event_type: str, summary: str, **kwargs: Any) -> AuditEvent: ...

    def list_events(self, task_id: str) -> list[AuditEvent]: ...


class CandidateRepository(Protocol):
    def create_candidate(self, task_id: str, candidate_type: str, display_name: str, **kwargs: Any) -> TaskCandidate: ...

    def get_candidate(self, candidate_id: str) -> TaskCandidate: ...

    def list_candidates(self, task_id: str) -> list[TaskCandidate]: ...

    def select_candidate(self, candidate_id: str, selected_by: str | None = None) -> TaskCandidate: ...


class UploadBatchRepository(Protocol):
    def create_batch(self, task_id: str, company_request: str, total_items: int, **kwargs: Any) -> UploadBatch: ...

    def get_batch(self, batch_id: str) -> UploadBatch: ...

    def update_batch(self, batch_id: str, **changes: Any) -> UploadBatch: ...


class UploadItemRepository(Protocol):
    def create_item(
        self,
        task_id: str,
        batch_id: str,
        item_order: int,
        requested_name: str,
        requested_type: AdvertisementType,
        **kwargs: Any,
    ) -> UploadItem: ...

    def get_item(self, item_id: str) -> UploadItem: ...

    def list_items(self, batch_id: str) -> list[UploadItem]: ...

    def update_item(self, item_id: str, **changes: Any) -> UploadItem: ...


class LocalAssetCandidateRepository(Protocol):
    def create_candidate(
        self,
        task_id: str,
        upload_item_id: str,
        file_name: str,
        local_path_ref: str,
        **kwargs: Any,
    ) -> LocalAssetCandidate: ...

    def get_candidate(self, candidate_id: str) -> LocalAssetCandidate: ...

    def list_candidates(self, upload_item_id: str) -> list[LocalAssetCandidate]: ...

    def select_candidate(self, candidate_id: str, selected_by: str | None = None) -> LocalAssetCandidate: ...


class InMemoryTaskRepository:
    def __init__(self) -> None:
        self._tasks: dict[str, AgentTask] = {}

    def create_task(self, original_command: str, agent_key: str, workflow_key: str) -> AgentTask:
        task = AgentTask(
            id=_new_id(),
            original_command=original_command,
            agent_key=agent_key,
            workflow_key=workflow_key,
        )
        self._tasks[task.id] = task
        return _copy(task)

    def get_task(self, task_id: str) -> AgentTask:
        return _copy(self._tasks[task_id])

    def update_task_status(self, task_id: str, status: TaskStatus) -> AgentTask:
        task = self._tasks[task_id]
        task.status = status
        task.updated_at = utc_now()
        if status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            task.completed_at = task.updated_at
        return _copy(task)

    def update_task(self, task_id: str, **changes: Any) -> AgentTask:
        task = self._tasks[task_id]
        for key, value in changes.items():
            setattr(task, key, _copy(value))
        task.updated_at = utc_now()
        if task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            task.completed_at = task.updated_at
        return _copy(task)


class InMemoryApprovalRepository:
    def __init__(self) -> None:
        self._approvals: dict[str, TaskApproval] = {}

    def create_approval(
        self,
        task_id: str,
        approval_type: ApprovalType,
        requested_payload: dict[str, Any] | None = None,
        subject_type: str = "task",
        subject_id: str | None = None,
    ) -> TaskApproval:
        approval = TaskApproval(
            id=_new_id(),
            task_id=task_id,
            approval_type=approval_type,
            subject_type=subject_type,
            subject_id=subject_id or task_id,
            requested_payload=_copy(requested_payload or {}),
        )
        self._approvals[approval.id] = approval
        return _copy(approval)

    def get_approval(self, approval_id: str) -> TaskApproval:
        return _copy(self._approvals[approval_id])

    def record_decision(
        self,
        approval_id: str,
        status: ApprovalStatus,
        decision_payload: dict[str, Any] | None = None,
        decided_by: str | None = None,
    ) -> TaskApproval:
        approval = self._approvals[approval_id]
        approval.status = status
        approval.decision_payload = _copy(decision_payload)
        approval.decided_by = decided_by
        approval.decided_at = utc_now()
        return _copy(approval)


class InMemoryAuditRepository:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record_event(self, task_id: str, event_type: str, summary: str, **kwargs: Any) -> AuditEvent:
        event = AuditEvent(id=_new_id(), task_id=task_id, event_type=event_type, summary=summary, **_copy(kwargs))
        self._events.append(event)
        return _copy(event)

    def list_events(self, task_id: str) -> list[AuditEvent]:
        return [_copy(event) for event in self._events if event.task_id == task_id]


class InMemoryCandidateRepository:
    def __init__(self) -> None:
        self._candidates: dict[str, TaskCandidate] = {}

    def create_candidate(self, task_id: str, candidate_type: str, display_name: str, **kwargs: Any) -> TaskCandidate:
        candidate = TaskCandidate(
            id=_new_id(),
            task_id=task_id,
            candidate_type=candidate_type,
            display_name=display_name,
            **_copy(kwargs),
        )
        self._candidates[candidate.id] = candidate
        return _copy(candidate)

    def get_candidate(self, candidate_id: str) -> TaskCandidate:
        return _copy(self._candidates[candidate_id])

    def list_candidates(self, task_id: str) -> list[TaskCandidate]:
        return [_copy(candidate) for candidate in self._candidates.values() if candidate.task_id == task_id]

    def select_candidate(self, candidate_id: str, selected_by: str | None = None) -> TaskCandidate:
        candidate = self._candidates[candidate_id]
        candidate.selection_status = "selected"
        candidate.selected_by = selected_by
        candidate.selected_at = utc_now()
        return _copy(candidate)


class InMemoryUploadBatchRepository:
    def __init__(self) -> None:
        self._batches: dict[str, UploadBatch] = {}

    def create_batch(self, task_id: str, company_request: str, total_items: int, **kwargs: Any) -> UploadBatch:
        batch = UploadBatch(
            id=_new_id(),
            task_id=task_id,
            company_request=company_request,
            total_items=total_items,
            **_copy(kwargs),
        )
        self._batches[batch.id] = batch
        return _copy(batch)

    def get_batch(self, batch_id: str) -> UploadBatch:
        return _copy(self._batches[batch_id])

    def update_batch(self, batch_id: str, **changes: Any) -> UploadBatch:
        batch = self._batches[batch_id]
        for key, value in changes.items():
            setattr(batch, key, _copy(value))
        batch.updated_at = utc_now()
        if batch.status in {"completed", "failed", "cancelled"}:
            batch.completed_at = batch.updated_at
        return _copy(batch)


class InMemoryUploadItemRepository:
    def __init__(self) -> None:
        self._items: dict[str, UploadItem] = {}

    def create_item(
        self,
        task_id: str,
        batch_id: str,
        item_order: int,
        requested_name: str,
        requested_type: AdvertisementType,
        **kwargs: Any,
    ) -> UploadItem:
        item = UploadItem(
            id=_new_id(),
            task_id=task_id,
            batch_id=batch_id,
            item_order=item_order,
            requested_name=requested_name,
            requested_type=requested_type,
            **_copy(kwargs),
        )
        self._items[item.id] = item
        return _copy(item)

    def get_item(self, item_id: str) -> UploadItem:
        return _copy(self._items[item_id])

    def list_items(self, batch_id: str) -> list[UploadItem]:
        items = [item for item in self._items.values() if item.batch_id == batch_id]
        return [_copy(item) for item in sorted(items, key=lambda item: item.item_order)]

    def update_item(self, item_id: str, **changes: Any) -> UploadItem:
        item = self._items[item_id]
        for key, value in changes.items():
            setattr(item, key, _copy(value))
        item.updated_at = utc_now()
        if item.status in {
            UploadItemStatus.SAVED,
            UploadItemStatus.FAILED,
            UploadItemStatus.SKIPPED,
            UploadItemStatus.CANCELLED,
        }:
            item.completed_at = item.updated_at
        return _copy(item)


class InMemoryLocalAssetCandidateRepository:
    def __init__(self) -> None:
        self._candidates: dict[str, LocalAssetCandidate] = {}

    def create_candidate(
        self,
        task_id: str,
        upload_item_id: str,
        file_name: str,
        local_path_ref: str,
        **kwargs: Any,
    ) -> LocalAssetCandidate:
        candidate = LocalAssetCandidate(
            id=_new_id(),
            task_id=task_id,
            upload_item_id=upload_item_id,
            file_name=file_name,
            local_path_ref=local_path_ref,
            **_copy(kwargs),
        )
        self._candidates[candidate.id] = candidate
        return _copy(candidate)

    def get_candidate(self, candidate_id: str) -> LocalAssetCandidate:
        return _copy(self._candidates[candidate_id])

    def list_candidates(self, upload_item_id: str) -> list[LocalAssetCandidate]:
        return [
            _copy(candidate)
            for candidate in self._candidates.values()
            if candidate.upload_item_id == upload_item_id
        ]

    def select_candidate(self, candidate_id: str, selected_by: str | None = None) -> LocalAssetCandidate:
        candidate = self._candidates[candidate_id]
        candidate.selection_status = "selected"
        candidate.selected_by = selected_by
        candidate.selected_at = utc_now()
        return _copy(candidate)
