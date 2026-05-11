from __future__ import annotations

from pathlib import Path

from backend.app.browser.adapters import AdUploadBrowserAdapter
from backend.app.db.repositories import (
    ApprovalRepository,
    AuditRepository,
    CandidateRepository,
    LocalAssetCandidateRepository,
    TaskRepository,
    UploadBatchRepository,
    UploadItemRepository,
)
from backend.app.safety.permissions import PermissionSet
from backend.app.workflows.ad_upload_graph import AdvertisementUploadGraphRunner, AdUploadWorkflowResult
from backend.app.workflows.state import UploadItem


class AdvertisementUploadAgent:
    def __init__(
        self,
        *,
        browser: AdUploadBrowserAdapter,
        asset_base_dirs: list[str | Path],
        task_repo: TaskRepository,
        approval_repo: ApprovalRepository,
        candidate_repo: CandidateRepository,
        batch_repo: UploadBatchRepository,
        item_repo: UploadItemRepository,
        asset_candidate_repo: LocalAssetCandidateRepository,
        audit_repo: AuditRepository,
        permissions: PermissionSet | None = None,
    ) -> None:
        self.item_repo = item_repo
        self._runner = AdvertisementUploadGraphRunner(
            browser=browser,
            asset_base_dirs=asset_base_dirs,
            task_repo=task_repo,
            approval_repo=approval_repo,
            candidate_repo=candidate_repo,
            batch_repo=batch_repo,
            item_repo=item_repo,
            asset_candidate_repo=asset_candidate_repo,
            audit_repo=audit_repo,
            permissions=permissions,
        )

    def create_upload_plan(self, command: str) -> AdUploadWorkflowResult:
        return self._runner.create_upload_plan(command)

    def approve_plan_and_start(self, task_id: str, approval_id: str, decided_by: str | None = None) -> AdUploadWorkflowResult:
        return self._runner.approve_plan_and_start(task_id, approval_id, decided_by=decided_by)

    def approve_tag_creation_and_continue(
        self,
        task_id: str,
        approval_id: str,
        decided_by: str | None = None,
    ) -> AdUploadWorkflowResult:
        return self._runner.approve_tag_creation_and_continue(task_id, approval_id, decided_by=decided_by)

    def approve_item_and_continue(
        self,
        task_id: str,
        approval_id: str,
        decided_by: str | None = None,
    ) -> AdUploadWorkflowResult:
        return self._runner.approve_item_and_continue(task_id, approval_id, decided_by=decided_by)

    def save_item_with_approval(self, task_id: str, item_id: str, approval_id: str) -> UploadItem:
        return self._runner.save_item_with_approval(task_id, item_id, approval_id)

    def skip_item_and_continue(self, task_id: str, item_id: str) -> AdUploadWorkflowResult:
        return self._runner.skip_item_and_continue(task_id, item_id)

    def retry_current_item(self, task_id: str, item_id: str) -> AdUploadWorkflowResult:
        return self._runner.retry_current_item(task_id, item_id)

    def change_item_asset_and_retry(
        self,
        task_id: str,
        item_id: str,
        local_asset_query: str,
    ) -> AdUploadWorkflowResult:
        return self._runner.change_item_asset_and_retry(task_id, item_id, local_asset_query)

    def cancel_remaining_items(self, task_id: str) -> AdUploadWorkflowResult:
        return self._runner.cancel_remaining_items(task_id)

    def manual_takeover(self, task_id: str) -> AdUploadWorkflowResult:
        return self._runner.manual_takeover(task_id)


__all__ = ["AdvertisementUploadAgent", "AdUploadWorkflowResult"]
