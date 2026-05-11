from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from backend.app.agents.router import RouteKind, TaskRouter
from backend.app.assets.local_search import search_local_assets
from backend.app.assets.media_validation import MediaValidationError, validate_asset_for_ad_type
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
from backend.app.safety.approvals import build_save_approval_request, verify_save_approval
from backend.app.safety.permissions import PermissionSet
from backend.app.workflows.state import (
    AdvertisementType,
    AgentTask,
    ApprovalStatus,
    ApprovalType,
    TaskApproval,
    TaskStatus,
    UploadBatch,
    UploadItem,
    UploadItemStatus,
)


@dataclass(frozen=True)
class AdUploadWorkflowResult:
    task: AgentTask
    batch: UploadBatch
    plan_approval: TaskApproval | None = None
    tag_creation_approval: TaskApproval | None = None
    item_save_approval: TaskApproval | None = None


class AdUploadGraphState(TypedDict, total=False):
    task_id: str
    batch_id: str
    item_id: str
    item_save_approval: TaskApproval
    failed: bool
    error_code: str
    error_message: str


class AdvertisementUploadGraphRunner:
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
        self.browser = browser
        self.asset_base_dirs = asset_base_dirs
        self.task_repo = task_repo
        self.approval_repo = approval_repo
        self.candidate_repo = candidate_repo
        self.batch_repo = batch_repo
        self.item_repo = item_repo
        self.asset_candidate_repo = asset_candidate_repo
        self.audit_repo = audit_repo
        self.permissions = permissions or PermissionSet.for_ad_upload_agent()
        self._task_batches: dict[str, str] = {}
        self.item_graph = self._build_item_graph()

    def create_upload_plan(self, command: str) -> AdUploadWorkflowResult:
        company_request, tag_request, asset_queries = self._parse_upload_plan(command)
        task = self.task_repo.create_task(
            original_command=command,
            agent_key="ad_upload_agent",
            workflow_key="advertisement_upload",
        )
        batch = self.batch_repo.create_batch(
            task_id=task.id,
            company_request=company_request,
            tag_request=tag_request,
            total_items=len(asset_queries),
        )
        self._task_batches[task.id] = batch.id
        for index, asset_query in enumerate(asset_queries, start=1):
            self.item_repo.create_item(
                task_id=task.id,
                batch_id=batch.id,
                item_order=index,
                requested_name=Path(asset_query).stem,
                requested_type=self._media_type_from_asset_query(asset_query),
                local_asset_query=asset_query,
            )
        items = self.item_repo.list_items(batch.id)
        self.task_repo.update_task(
            task.id,
            status=TaskStatus.AWAITING_UPLOAD_PLAN_CONFIRMATION,
            parsed_command={
                "company_request": company_request,
                "tag_request": tag_request,
                "items": [
                    {
                        "item_order": item.item_order,
                        "requested_name": item.requested_name,
                        "requested_type": item.requested_type.value,
                        "local_asset_query": item.local_asset_query,
                    }
                    for item in items
                ],
            },
            awaiting_action="owner_upload_plan_confirmation",
        )
        approval = self.approval_repo.create_approval(
            task_id=task.id,
            approval_type=ApprovalType.COMMAND_CONFIRMATION,
            requested_payload=self.task_repo.get_task(task.id).parsed_command or {},
            subject_type="upload_batch",
            subject_id=batch.id,
        )
        self.audit_repo.record_event(task.id, "upload_plan_created", "Advertisement upload plan created")
        return AdUploadWorkflowResult(
            task=self.task_repo.get_task(task.id),
            batch=self.batch_repo.get_batch(batch.id),
            plan_approval=approval,
        )

    def approve_plan_and_start(self, task_id: str, approval_id: str, decided_by: str | None = None) -> AdUploadWorkflowResult:
        approval = self.approval_repo.record_decision(
            approval_id,
            ApprovalStatus.APPROVED,
            decision_payload={"confirmed": True},
            decided_by=decided_by,
        )
        batch = self._batch_for_task(task_id)
        if approval.subject_id != batch.id:
            raise ValueError("approval does not authorize this upload batch")
        self.task_repo.update_task_status(task_id, TaskStatus.RUNNING)
        self.batch_repo.update_batch(batch.id, status="running")
        return self._resolve_company_and_tag(task_id, batch.id)

    def approve_tag_creation_and_continue(
        self,
        task_id: str,
        approval_id: str,
        decided_by: str | None = None,
    ) -> AdUploadWorkflowResult:
        approval = self.approval_repo.record_decision(
            approval_id,
            ApprovalStatus.APPROVED,
            decision_payload={"confirmed": True},
            decided_by=decided_by,
        )
        batch = self._batch_for_task(task_id)
        if approval.subject_id != batch.id:
            raise ValueError("approval does not authorize this upload batch")
        company_id = str(approval.requested_payload["company_id"])
        tag_name = str(approval.requested_payload["tag_name"])
        self.permissions.require("create_tag_after_owner_approval")
        tag = self.browser.create_tag_after_approval(company_id, tag_name)
        self.browser.select_tag(tag.id)
        self.batch_repo.update_batch(
            batch.id,
            created_tag={"id": tag.id, "name": tag.name, "company_id": tag.company_id},
            matched_tag={"id": tag.id, "name": tag.name, "company_id": tag.company_id},
            status="running",
        )
        self.audit_repo.record_event(task_id, "tag_created", "Advertisement tag created", details={"tag_id": tag.id})
        return self._process_next_item(task_id, batch.id)

    def approve_item_and_continue(
        self,
        task_id: str,
        approval_id: str,
        decided_by: str | None = None,
    ) -> AdUploadWorkflowResult:
        approval = self.approval_repo.record_decision(
            approval_id,
            ApprovalStatus.APPROVED,
            decision_payload={"confirmed": True},
            decided_by=decided_by,
        )
        saved_item = self.save_item_with_approval(task_id, approval.subject_id, approval.id)
        if saved_item.status != UploadItemStatus.SAVED:
            return self._result(task_id)
        return self._process_next_item(task_id, saved_item.batch_id)

    def save_item_with_approval(self, task_id: str, item_id: str, approval_id: str) -> UploadItem:
        approval = self.approval_repo.get_approval(approval_id)
        if approval.subject_type != "upload_item" or approval.subject_id != item_id:
            raise ValueError("approval does not authorize current item")
        item = self.item_repo.get_item(item_id)
        if item.status != UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL:
            raise ValueError("item is not awaiting save approval")
        verify_save_approval(approval, item.preview_payload)
        self.permissions.require("save_ad_after_owner_approval")
        result = self.browser.save_ad_after_approval()
        self.permissions.require("read_saved_ad_result")
        self.browser.read_saved_ad_result()
        if not result.succeeded or result.saved_ad is None:
            return self.item_repo.update_item(item.id, status=UploadItemStatus.FAILED, error_code="save_failed")
        saved_item = self.item_repo.update_item(
            item.id,
            status=UploadItemStatus.SAVED,
            saved_ad={
                "id": result.saved_ad.id,
                "name": result.saved_ad.name,
                "type": result.saved_ad.ad_type.value,
            },
        )
        self._refresh_batch_counts(item.batch_id)
        self.audit_repo.record_event(task_id, "upload_item_saved", "Advertisement upload item saved")
        return saved_item

    def skip_item_and_continue(self, task_id: str, item_id: str) -> AdUploadWorkflowResult:
        item = self.item_repo.update_item(item_id, status=UploadItemStatus.SKIPPED)
        self._refresh_batch_counts(item.batch_id)
        return self._process_next_item(task_id, item.batch_id)

    def retry_current_item(self, task_id: str, item_id: str) -> AdUploadWorkflowResult:
        item = self._reset_item_for_retry(task_id, item_id)
        final_state = self.item_graph.invoke({"task_id": task_id, "batch_id": item.batch_id, "item_id": item.id})
        return self._result(task_id, item_save_approval=final_state.get("item_save_approval"))

    def change_item_asset_and_retry(
        self,
        task_id: str,
        item_id: str,
        local_asset_query: str,
    ) -> AdUploadWorkflowResult:
        self.item_repo.update_item(item_id, local_asset_query=local_asset_query)
        return self.retry_current_item(task_id, item_id)

    def cancel_remaining_items(self, task_id: str) -> AdUploadWorkflowResult:
        batch = self._batch_for_task(task_id)
        for item in self.item_repo.list_items(batch.id):
            if item.status in {
                UploadItemStatus.PENDING,
                UploadItemStatus.READY_TO_UPLOAD,
                UploadItemStatus.UPLOADING,
                UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL,
            }:
                self.item_repo.update_item(item.id, status=UploadItemStatus.CANCELLED)
        self.batch_repo.update_batch(batch.id, status="cancelled")
        self.task_repo.update_task_status(task_id, TaskStatus.CANCELLED)
        return self._result(task_id)

    def manual_takeover(self, task_id: str) -> AdUploadWorkflowResult:
        batch = self._batch_for_task(task_id)
        self.batch_repo.update_batch(batch.id, status="manual_takeover")
        self.task_repo.update_task(task_id, status=TaskStatus.CANCELLED, awaiting_action="manual_takeover")
        return self._result(task_id)

    def _resolve_company_and_tag(self, task_id: str, batch_id: str) -> AdUploadWorkflowResult:
        batch = self.batch_repo.get_batch(batch_id)
        self.permissions.require("check_login")
        if not self.browser.check_login().logged_in:
            task = self.task_repo.update_task(task_id, status=TaskStatus.AWAITING_LOGIN, awaiting_action="manual_login")
            return AdUploadWorkflowResult(task=task, batch=self.batch_repo.get_batch(batch_id))
        self.permissions.require("open_ad_management")
        self.browser.open_ad_management()
        self.permissions.require("search_company")
        companies = self.browser.search_company(batch.company_request)
        if len(companies) != 1:
            task = self.task_repo.update_task(
                task_id,
                status=TaskStatus.AWAITING_COMPANY_SELECTION if companies else TaskStatus.FAILED,
                error_code="company_match_not_unique" if companies else "company_not_found",
            )
            return AdUploadWorkflowResult(task=task, batch=batch)
        company = companies[0]
        self.permissions.require("select_owner_approved_company")
        self.browser.select_company(company.id)
        self.batch_repo.update_batch(batch_id, matched_company={"id": company.id, "name": company.name})

        tag_request = batch.tag_request or ""
        self.permissions.require("search_tag")
        tags = self.browser.search_tag(company.id, tag_request)
        if len(tags) > 1:
            task = self.task_repo.update_task(
                task_id,
                status=TaskStatus.AWAITING_TAG_SELECTION,
                error_code="tag_match_not_unique",
                awaiting_action="owner_tag_selection",
            )
            return AdUploadWorkflowResult(task=task, batch=self.batch_repo.get_batch(batch_id))
        if not tags:
            approval = self.approval_repo.create_approval(
                task_id=task_id,
                approval_type=ApprovalType.COMMAND_CONFIRMATION,
                requested_payload={"company_id": company.id, "company_name": company.name, "tag_name": tag_request},
                subject_type="upload_batch",
                subject_id=batch_id,
            )
            task = self.task_repo.update_task(
                task_id,
                status=TaskStatus.AWAITING_TAG_CREATION_CONFIRMATION,
                awaiting_action="owner_tag_creation_confirmation",
            )
            self.batch_repo.update_batch(batch_id, status="awaiting_tag_creation_confirmation")
            return AdUploadWorkflowResult(
                task=task,
                batch=self.batch_repo.get_batch(batch_id),
                tag_creation_approval=approval,
            )

        tag = tags[0]
        self.permissions.require("select_owner_approved_tag")
        self.browser.select_tag(tag.id)
        self.batch_repo.update_batch(batch_id, matched_tag={"id": tag.id, "name": tag.name, "company_id": tag.company_id})
        return self._process_next_item(task_id, batch_id)

    def _process_next_item(self, task_id: str, batch_id: str) -> AdUploadWorkflowResult:
        active_statuses = {UploadItemStatus.UPLOADING, UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL}
        items = self.item_repo.list_items(batch_id)
        if any(item.status in active_statuses for item in items):
            return self._result(task_id)
        next_item = next((item for item in items if item.status == UploadItemStatus.PENDING), None)
        if next_item is None:
            self.batch_repo.update_batch(batch_id, status="completed")
            task = self.task_repo.update_task_status(task_id, TaskStatus.SUCCEEDED)
            return AdUploadWorkflowResult(task=task, batch=self.batch_repo.get_batch(batch_id))
        final_state = self.item_graph.invoke({"task_id": task_id, "batch_id": batch_id, "item_id": next_item.id})
        return self._result(task_id, item_save_approval=final_state.get("item_save_approval"))

    def _build_item_graph(self):
        graph = StateGraph(AdUploadGraphState)
        graph.add_node("search_local_asset", self._search_local_asset)
        graph.add_node("upload_asset", self._upload_asset)
        graph.add_node("create_item_save_approval", self._create_item_save_approval)
        graph.add_node("finish_item_failure", self._finish_item_failure)
        graph.set_entry_point("search_local_asset")
        graph.add_conditional_edges(
            "search_local_asset",
            self._continue_or_fail,
            {"continue": "upload_asset", "fail": "finish_item_failure"},
        )
        graph.add_conditional_edges(
            "upload_asset",
            self._continue_or_fail,
            {"continue": "create_item_save_approval", "fail": "finish_item_failure"},
        )
        graph.add_edge("create_item_save_approval", END)
        graph.add_edge("finish_item_failure", END)
        return graph.compile()

    def _search_local_asset(self, state: AdUploadGraphState) -> AdUploadGraphState:
        item = self.item_repo.get_item(state["item_id"])
        self.permissions.require("search_local_assets")
        results = search_local_assets(
            item.local_asset_query or item.requested_name,
            media_type=item.requested_type,
            base_dirs=self.asset_base_dirs,
        )
        for result in results:
            self.asset_candidate_repo.create_candidate(
                task_id=state["task_id"],
                upload_item_id=item.id,
                file_name=result.file_name,
                local_path_ref=result.local_path_ref,
                media_type=result.media_type,
                metadata={"size_bytes": result.size_bytes, "extension": result.extension},
            )
        if not results:
            self.item_repo.update_item(item.id, status=UploadItemStatus.FAILED, error_code="asset_not_found")
            return self._failed_state(state, "asset_not_found", "No matching local asset found")
        if len(results) > 1:
            self.item_repo.update_item(item.id, status=UploadItemStatus.AWAITING_ASSET_SELECTION)
            return self._failed_state(state, "multiple_asset_candidates", "Multiple local assets matched")
        try:
            metadata = validate_asset_for_ad_type(results[0].local_path_ref, item.requested_type)
        except MediaValidationError as exc:
            self.item_repo.update_item(item.id, status=UploadItemStatus.FAILED, error_code="media_type_mismatch")
            return self._failed_state(state, "media_type_mismatch", str(exc))
        self.item_repo.update_item(
            item.id,
            status=UploadItemStatus.READY_TO_UPLOAD,
            selected_asset_path=metadata.local_path_ref,
            selected_asset_metadata={
                "file_name": metadata.file_name,
                "extension": metadata.extension,
                "size_bytes": metadata.size_bytes,
                "media_type": metadata.media_type.value,
            },
        )
        return state

    def _upload_asset(self, state: AdUploadGraphState) -> AdUploadGraphState:
        item = self.item_repo.get_item(state["item_id"])
        batch = self.batch_repo.get_batch(state["batch_id"])
        if item.selected_asset_path is None:
            return self._failed_state(state, "asset_not_selected", "A local asset must be selected before upload")
        self.item_repo.update_item(item.id, status=UploadItemStatus.UPLOADING)
        self.permissions.require("open_ad_create_form")
        self.browser.open_ad_create_form()
        self.permissions.require("select_ad_type")
        self.browser.select_ad_type(item.requested_type)
        form_payload = {
            "name": item.requested_name,
            "category": item.requested_category,
            "company": batch.matched_company,
            "tag": batch.matched_tag or batch.created_tag,
        }
        self.permissions.require("fill_ad_metadata")
        self.browser.fill_ad_metadata(form_payload)
        self.permissions.require("upload_local_asset")
        self.browser.upload_local_asset(item.selected_asset_path)
        self.permissions.require("read_ad_preview")
        preview = self.browser.read_ad_preview()
        report = {
            "task_id": state["task_id"],
            "batch_id": state["batch_id"],
            "item_id": item.id,
            "item_order": item.item_order,
            "company": batch.matched_company,
            "tag": batch.matched_tag or batch.created_tag,
            "advertisement_name": item.requested_name,
            "advertisement_type": item.requested_type.value,
            "selected_asset_path": item.selected_asset_path,
            "selected_asset_metadata": item.selected_asset_metadata,
            "preview": {"id": preview.id, "name": preview.name, "type": preview.ad_type.value},
            "safety_statement": (
                "This item save will not bind advertisements to devices, delete data, overwrite existing "
                "advertisements, or modify company information."
            ),
        }
        self.item_repo.update_item(
            item.id,
            status=UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL,
            form_payload=form_payload,
            preview_payload=report,
        )
        self.task_repo.update_task(
            state["task_id"],
            status=TaskStatus.AWAITING_ITEM_SAVE_APPROVAL,
            awaiting_action="owner_item_save_approval",
        )
        return state

    def _create_item_save_approval(self, state: AdUploadGraphState) -> AdUploadGraphState:
        item = self.item_repo.get_item(state["item_id"])
        approval = self.approval_repo.create_approval(
            task_id=state["task_id"],
            approval_type=ApprovalType.SAVE_APPROVAL,
            requested_payload=build_save_approval_request(item.preview_payload),
            subject_type="upload_item",
            subject_id=item.id,
        )
        self.audit_repo.record_event(state["task_id"], "item_save_approval_requested", "Item save approval requested")
        return {**state, "item_save_approval": approval}

    def _finish_item_failure(self, state: AdUploadGraphState) -> AdUploadGraphState:
        self.task_repo.update_task(
            state["task_id"],
            status=TaskStatus.FAILED,
            error_code=state["error_code"],
            error_message=state["error_message"],
        )
        return state

    def _parse_upload_plan(self, command: str) -> tuple[str, str, list[str]]:
        route = TaskRouter().route(command)
        if route.kind not in {RouteKind.AD_UPLOAD, RouteKind.MIXED_UPLOAD_THEN_BIND}:
            raise ValueError("command is not an advertisement upload request")
        if not route.company_query:
            raise ValueError("company is required for advertisement upload")
        if not route.tag_query:
            raise ValueError("tag is required for advertisement upload")
        if not route.upload_asset_queries:
            raise ValueError("at least one local asset query is required")
        return self._normalize_company_query(route.company_query), route.tag_query, route.upload_asset_queries

    def _normalize_company_query(self, company_query: str) -> str:
        if company_query.startswith("企业") and len(company_query) > 2:
            return f"Company {company_query[2:]}"
        return company_query

    def _media_type_from_asset_query(self, asset_query: str) -> AdvertisementType:
        extension = Path(asset_query).suffix.lower()
        if extension in {".jpg", ".jpeg", ".png", ".webp"}:
            return AdvertisementType.IMAGE
        if extension in {".mp4", ".mov", ".webm"}:
            return AdvertisementType.VIDEO
        return AdvertisementType.UNKNOWN

    def _batch_for_task(self, task_id: str) -> UploadBatch:
        return self.batch_repo.get_batch(self._task_batches[task_id])

    def _refresh_batch_counts(self, batch_id: str) -> None:
        items = self.item_repo.list_items(batch_id)
        completed_items = len([item for item in items if item.status == UploadItemStatus.SAVED])
        failed_items = len([item for item in items if item.status == UploadItemStatus.FAILED])
        skipped_items = len([item for item in items if item.status == UploadItemStatus.SKIPPED])
        self.batch_repo.update_batch(
            batch_id,
            completed_items=completed_items,
            failed_items=failed_items,
            skipped_items=skipped_items,
        )

    def _reset_item_for_retry(self, task_id: str, item_id: str) -> UploadItem:
        item = self.item_repo.get_item(item_id)
        if item.task_id != task_id:
            raise ValueError("item does not belong to task")
        self.task_repo.update_task(task_id, status=TaskStatus.RUNNING, error_code=None, error_message=None)
        return self.item_repo.update_item(
            item.id,
            status=UploadItemStatus.PENDING,
            selected_asset_path=None,
            selected_asset_metadata={},
            form_payload={},
            preview_payload={},
            error_code=None,
            error_message=None,
        )

    def _result(
        self,
        task_id: str,
        *,
        item_save_approval: TaskApproval | None = None,
    ) -> AdUploadWorkflowResult:
        batch = self._batch_for_task(task_id)
        return AdUploadWorkflowResult(
            task=self.task_repo.get_task(task_id),
            batch=batch,
            item_save_approval=item_save_approval,
        )

    def _failed_state(self, state: AdUploadGraphState, error_code: str, error_message: str) -> AdUploadGraphState:
        return {**state, "failed": True, "error_code": error_code, "error_message": error_message}

    def _continue_or_fail(self, state: AdUploadGraphState) -> str:
        return "fail" if state.get("failed") else "continue"
