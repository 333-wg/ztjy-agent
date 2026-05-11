from __future__ import annotations

from typing import Any

from backend.app.browser.adapters import DeviceAdBrowserAdapter
from backend.app.db.repositories import (
    ApprovalRepository,
    AuditRepository,
    CandidateRepository,
    TaskRepository,
)
from backend.app.safety.permissions import PermissionSet
from backend.app.workflows.device_ad_graph import (
    DeviceAdGraphRunner,
    DeviceAdPrepareResult,
    DeviceAdWorkflowError,
)
from backend.app.workflows.state import AdvertisementRequest, AgentTask


class DeviceAdvertisementAgent:
    def __init__(
        self,
        *,
        browser: DeviceAdBrowserAdapter,
        task_repo: TaskRepository,
        approval_repo: ApprovalRepository,
        candidate_repo: CandidateRepository,
        audit_repo: AuditRepository,
        permissions: PermissionSet | None = None,
        checkpointer: Any | None = None,
    ) -> None:
        self._runner = DeviceAdGraphRunner(
            browser=browser,
            task_repo=task_repo,
            approval_repo=approval_repo,
            candidate_repo=candidate_repo,
            audit_repo=audit_repo,
            permissions=permissions,
            checkpointer=checkpointer,
        )

    def prepare_binding(
        self,
        *,
        original_command: str,
        target_device_no: str,
        requested_ads: list[AdvertisementRequest],
    ) -> DeviceAdPrepareResult:
        return self._runner.prepare(
            original_command=original_command,
            target_device_no=target_device_no,
            requested_ads=requested_ads,
        )

    def approve_and_save(self, task_id: str, approval_id: str, decided_by: str | None = None) -> AgentTask:
        return self._runner.approve_and_save(task_id, approval_id, decided_by=decided_by)

    def save_with_approval(self, task_id: str, approval_id: str) -> AgentTask:
        return self._runner.save_with_approval(task_id, approval_id)

    def validate_correction_removal(self, task_id: str, ad_ids: list[str]) -> list[str]:
        return self._runner.validate_correction_removal(task_id, ad_ids)


__all__ = ["DeviceAdvertisementAgent", "DeviceAdPrepareResult", "DeviceAdWorkflowError"]
