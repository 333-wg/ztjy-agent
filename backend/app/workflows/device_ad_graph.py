from __future__ import annotations

from dataclasses import dataclass

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from backend.app.browser.adapters import AdvertisementRecord, DeviceAdBrowserAdapter, DeviceRecord
from backend.app.db.repositories import (
    ApprovalRepository,
    AuditRepository,
    CandidateRepository,
    TaskRepository,
)
from backend.app.safety.approvals import build_save_approval_request, verify_save_approval
from backend.app.safety.permissions import PermissionSet
from backend.app.workflows.state import (
    AdvertisementRequest,
    AgentTask,
    ApprovalStatus,
    ApprovalType,
    DeviceMatch,
    MatchedAdvertisement,
    TaskApproval,
    TaskStatus,
)


class DeviceAdWorkflowError(Exception):
    pass


class DeviceAdGraphState(TypedDict, total=False):
    task_id: str
    target_device_no: str
    requested_ads: list[AdvertisementRequest]
    matched_device: DeviceRecord
    baseline_ads: list[AdvertisementRecord]
    matched_ads: list[AdvertisementRecord]
    pending_ads: list[AdvertisementRecord]
    save_approval: TaskApproval
    failed: bool
    failure_status: TaskStatus
    error_code: str
    error_message: str


@dataclass(frozen=True)
class DeviceAdPrepareResult:
    task: AgentTask
    save_approval: TaskApproval | None = None


def to_device_match(device: DeviceRecord) -> DeviceMatch:
    return DeviceMatch(
        device_no=device.device_no,
        external_ref=device.id,
        display_name=device.display_name,
        metadata=device.metadata,
    )


def to_matched_ad(ad: AdvertisementRecord) -> MatchedAdvertisement:
    return MatchedAdvertisement(
        name=ad.name,
        ad_type=ad.ad_type,
        external_ref=ad.id,
        category=ad.category,
        metadata=ad.metadata,
    )


class DeviceAdGraphRunner:
    def __init__(
        self,
        browser: DeviceAdBrowserAdapter,
        task_repo: TaskRepository,
        approval_repo: ApprovalRepository,
        candidate_repo: CandidateRepository,
        audit_repo: AuditRepository,
        permissions: PermissionSet | None = None,
    ) -> None:
        self.browser = browser
        self.task_repo = task_repo
        self.approval_repo = approval_repo
        self.candidate_repo = candidate_repo
        self.audit_repo = audit_repo
        self.permissions = permissions or PermissionSet.for_device_ad_agent()
        self.graph = self._build_graph()

    def prepare(
        self,
        *,
        original_command: str,
        target_device_no: str,
        requested_ads: list[AdvertisementRequest],
    ) -> DeviceAdPrepareResult:
        task = self.task_repo.create_task(
            original_command=original_command,
            agent_key="device_ad_agent",
            workflow_key="device_ad_binding",
        )
        self.task_repo.update_task(
            task.id,
            status=TaskStatus.RUNNING,
            target_device_no=target_device_no,
            requested_ads=requested_ads,
            parsed_command={
                "target_device_no": target_device_no,
                "requested_ads": [request.model_dump(mode="json") for request in requested_ads],
            },
        )
        self.audit_repo.record_event(task.id, "task_created", "Device advertisement binding started")

        final_state = self.graph.invoke(
            {
                "task_id": task.id,
                "target_device_no": target_device_no,
                "requested_ads": requested_ads,
            }
        )
        saved_task = self.task_repo.get_task(task.id)
        return DeviceAdPrepareResult(
            task=saved_task,
            save_approval=final_state.get("save_approval"),
        )

    def approve_and_save(self, task_id: str, approval_id: str, decided_by: str | None = None) -> AgentTask:
        approval = self.approval_repo.record_decision(
            approval_id,
            ApprovalStatus.APPROVED,
            decision_payload={"confirmed": True},
            decided_by=decided_by,
        )
        return self.save_with_approval(task_id, approval.id)

    def save_with_approval(self, task_id: str, approval_id: str) -> AgentTask:
        self.permissions.require("save_after_owner_approval")
        task = self.task_repo.get_task(task_id)
        if task.pending_save_report is None:
            raise DeviceAdWorkflowError("pending save report is required before saving")
        approval = self.approval_repo.get_approval(approval_id)
        verify_save_approval(approval, task.pending_save_report)
        self.task_repo.update_task_status(task_id, TaskStatus.SAVING)
        result = self.browser.save_after_approval()
        self.permissions.require("read_save_result")
        self.browser.read_save_result()
        if not result.succeeded:
            self.audit_repo.record_event(task_id, "save_failed", result.message or "Device advertisement save failed")
            return self._fail_task(task_id, "save_failed", result.message or "Save failed")
        self.audit_repo.record_event(
            task_id,
            "save_succeeded",
            "Device advertisements saved",
            details={"saved_ids": result.saved_ids},
        )
        return self.task_repo.update_task_status(task_id, TaskStatus.SUCCEEDED)

    def validate_correction_removal(self, task_id: str, ad_ids: list[str]) -> list[str]:
        task = self.task_repo.get_task(task_id)
        task_added_ids = {ad.external_ref for ad in task.task_added_ads}
        baseline_ids = {ad.external_ref for ad in task.baseline_ads}
        for ad_id in ad_ids:
            if ad_id in baseline_ids:
                raise DeviceAdWorkflowError("baseline advertisements cannot be removed by correction")
            if ad_id not in task_added_ids:
                raise DeviceAdWorkflowError(f"advertisement was not added by this task: {ad_id}")
        return ad_ids

    def _build_graph(self):
        graph = StateGraph(DeviceAdGraphState)
        graph.add_node("check_login", self._check_login)
        graph.add_node("search_device", self._search_device)
        graph.add_node("read_baseline", self._read_baseline)
        graph.add_node("search_ads", self._search_ads)
        graph.add_node("add_pending_ads", self._add_pending_ads)
        graph.add_node("pre_save_verify", self._pre_save_verify)
        graph.add_node("create_save_approval", self._create_save_approval)
        graph.add_node("finish_failed", self._finish_failed)
        graph.set_entry_point("check_login")
        graph.add_conditional_edges("check_login", self._continue_or_fail, {"continue": "search_device", "fail": "finish_failed"})
        graph.add_conditional_edges("search_device", self._continue_or_fail, {"continue": "read_baseline", "fail": "finish_failed"})
        graph.add_conditional_edges("read_baseline", self._continue_or_fail, {"continue": "search_ads", "fail": "finish_failed"})
        graph.add_conditional_edges("search_ads", self._continue_or_fail, {"continue": "add_pending_ads", "fail": "finish_failed"})
        graph.add_conditional_edges("add_pending_ads", self._continue_or_fail, {"continue": "pre_save_verify", "fail": "finish_failed"})
        graph.add_conditional_edges(
            "pre_save_verify",
            self._approval_or_fail,
            {"approval": "create_save_approval", "fail": "finish_failed"},
        )
        graph.add_edge("create_save_approval", END)
        graph.add_edge("finish_failed", END)
        return graph.compile()

    def _check_login(self, state: DeviceAdGraphState) -> DeviceAdGraphState:
        self.permissions.require("check_login")
        login = self.browser.check_login()
        if not login.logged_in:
            return self._failed_state(
                state,
                status=TaskStatus.AWAITING_LOGIN,
                error_code="login_required",
                error_message=login.reason or "Management backend login is required",
            )
        return state

    def _search_device(self, state: DeviceAdGraphState) -> DeviceAdGraphState:
        self.permissions.require("open_device_management")
        self.browser.open_device_management()
        self.permissions.require("search_device")
        devices = self.browser.search_device(state["target_device_no"])
        if not devices:
            return self._failed_state(state, error_code="device_not_found", error_message="No matching device found")
        if len(devices) > 1:
            return self._failed_state(
                state,
                status=TaskStatus.AWAITING_CANDIDATE_SELECTION,
                error_code="multiple_device_candidates",
                error_message="Multiple matching devices found",
            )
        device = devices[0]
        self.permissions.require("open_device_ad_config")
        self.browser.open_device_ad_config(device.id)
        self.task_repo.update_task(state["task_id"], matched_device=to_device_match(device))
        return {**state, "matched_device": device}

    def _read_baseline(self, state: DeviceAdGraphState) -> DeviceAdGraphState:
        baseline_ads = self.browser.read_existing_device_ads()
        self.task_repo.update_task(
            state["task_id"],
            baseline_ads=[to_matched_ad(ad) for ad in baseline_ads],
        )
        return {**state, "baseline_ads": baseline_ads}

    def _search_ads(self, state: DeviceAdGraphState) -> DeviceAdGraphState:
        matched_ads: list[AdvertisementRecord] = []
        for request in state["requested_ads"]:
            self.permissions.require("search_existing_ads")
            if request.ad_type.value != "unknown":
                self.permissions.require("filter_ads_by_type")
            if request.category is not None:
                self.permissions.require("filter_ads_by_category")
            candidates = self.browser.search_ads(
                request.name,
                ad_type=None if request.ad_type.value == "unknown" else request.ad_type,
                category=request.category,
            )
            if not candidates:
                return self._failed_state(
                    state,
                    error_code="advertisement_not_found",
                    error_message=f"Advertisement not found: {request.name}",
                )
            if len(candidates) > 1:
                for candidate in candidates:
                    self.candidate_repo.create_candidate(
                        task_id=state["task_id"],
                        candidate_type="advertisement",
                        display_name=candidate.name,
                        external_ref=candidate.id,
                        ad_type=candidate.ad_type,
                        category=candidate.category,
                        metadata=candidate.metadata,
                    )
                return self._failed_state(
                    state,
                    status=TaskStatus.AWAITING_CANDIDATE_SELECTION,
                    error_code="multiple_ad_candidates",
                    error_message=f"Multiple advertisement candidates found: {request.name}",
                )
            matched_ads.append(candidates[0])
        self.task_repo.update_task(
            state["task_id"],
            matched_ads=[to_matched_ad(ad) for ad in matched_ads],
        )
        return {**state, "matched_ads": matched_ads}

    def _add_pending_ads(self, state: DeviceAdGraphState) -> DeviceAdGraphState:
        self.permissions.require("select_owner_approved_ads")
        ad_ids = [ad.id for ad in state["matched_ads"]]
        self.permissions.require("add_selected_ad_to_pending_list")
        self.browser.select_ads(ad_ids)
        self.permissions.require("read_pending_ads")
        pending_ads = self.browser.read_pending_ads()
        baseline_ids = {ad.id for ad in state["baseline_ads"]}
        task_added_ads = [ad for ad in pending_ads if ad.id in ad_ids and ad.id not in baseline_ids]
        self.task_repo.update_task(
            state["task_id"],
            task_added_ads=[to_matched_ad(ad) for ad in task_added_ads],
        )
        return {**state, "pending_ads": pending_ads}

    def _pre_save_verify(self, state: DeviceAdGraphState) -> DeviceAdGraphState:
        baseline_ids = {ad.id for ad in state["baseline_ads"]}
        pending_ids = {ad.id for ad in state["pending_ads"]}
        missing_baseline_ids = sorted(baseline_ids - pending_ids)
        if missing_baseline_ids:
            return self._failed_state(
                state,
                status=TaskStatus.AWAITING_CORRECTION_DECISION,
                error_code="baseline_ad_missing",
                error_message="Pending page state is missing baseline advertisements",
            )

        matched_ids = {matched.id for matched in state["matched_ads"]}
        task_added_ads = [
            ad for ad in state["pending_ads"] if ad.id in matched_ids and ad.id not in baseline_ids
        ]
        report = {
            "original_command": self.task_repo.get_task(state["task_id"]).original_command,
            "target_device_no": state["target_device_no"],
            "matched_device": {
                "id": state["matched_device"].id,
                "device_no": state["matched_device"].device_no,
                "display_name": state["matched_device"].display_name,
            },
            "baseline_ads": [self._ad_report(ad) for ad in state["baseline_ads"]],
            "requested_ads": [request.model_dump(mode="json") for request in state["requested_ads"]],
            "matched_ads": [self._ad_report(ad) for ad in state["matched_ads"]],
            "task_added_ads": [self._ad_report(ad) for ad in task_added_ads],
            "pending_ads": [self._ad_report(ad) for ad in state["pending_ads"]],
            "safety_statement": (
                "No advertisements were created or deleted, no baseline advertisements were removed, "
                "and no device profile fields were modified."
            ),
        }
        self.task_repo.update_task(
            state["task_id"],
            pending_save_report=report,
            status=TaskStatus.AWAITING_SAVE_APPROVAL,
            awaiting_action="owner_save_approval",
        )
        self.audit_repo.record_event(state["task_id"], "pre_save_report_created", "Pre-save verification report created")
        return state

    def _create_save_approval(self, state: DeviceAdGraphState) -> DeviceAdGraphState:
        task = self.task_repo.get_task(state["task_id"])
        if task.pending_save_report is None:
            raise DeviceAdWorkflowError("pending save report is required")
        approval = self.approval_repo.create_approval(
            task_id=state["task_id"],
            approval_type=ApprovalType.SAVE_APPROVAL,
            requested_payload=build_save_approval_request(task.pending_save_report),
            subject_type="task",
            subject_id=state["task_id"],
        )
        self.audit_repo.record_event(state["task_id"], "save_approval_requested", "Owner save approval requested")
        return {**state, "save_approval": approval}

    def _finish_failed(self, state: DeviceAdGraphState) -> DeviceAdGraphState:
        self._fail_task(
            state["task_id"],
            state["error_code"],
            state["error_message"],
            status=state.get("failure_status", TaskStatus.FAILED),
        )
        return state

    def _fail_task(
        self,
        task_id: str,
        error_code: str,
        error_message: str,
        status: TaskStatus = TaskStatus.FAILED,
    ) -> AgentTask:
        self.audit_repo.record_event(task_id, "workflow_blocked", error_message, severity="warning")
        return self.task_repo.update_task(
            task_id,
            status=status,
            error_code=error_code,
            error_message=error_message,
            awaiting_action="owner_decision" if status != TaskStatus.FAILED else None,
        )

    def _failed_state(
        self,
        state: DeviceAdGraphState,
        *,
        error_code: str,
        error_message: str,
        status: TaskStatus = TaskStatus.FAILED,
    ) -> DeviceAdGraphState:
        return {
            **state,
            "failed": True,
            "failure_status": status,
            "error_code": error_code,
            "error_message": error_message,
        }

    def _continue_or_fail(self, state: DeviceAdGraphState) -> str:
        return "fail" if state.get("failed") else "continue"

    def _approval_or_fail(self, state: DeviceAdGraphState) -> str:
        return "fail" if state.get("failed") else "approval"

    def _ad_report(self, ad: AdvertisementRecord) -> dict[str, object]:
        return {
            "id": ad.id,
            "name": ad.name,
            "type": ad.ad_type.value,
            "category": ad.category,
        }
