import pytest

from backend.app.safety.approvals import (
    ApprovalGateError,
    build_save_approval_request,
    compute_approval_payload_hash,
    verify_save_approval,
)
from backend.app.safety.permissions import PermissionDenied, PermissionSet
from backend.app.workflows.state import ApprovalStatus, ApprovalType, TaskApproval


def test_device_agent_cannot_upload_advertisements():
    permissions = PermissionSet.for_device_ad_agent()

    with pytest.raises(PermissionDenied):
        permissions.require("upload_local_asset")


def test_upload_agent_cannot_bind_devices():
    permissions = PermissionSet.for_ad_upload_agent()

    with pytest.raises(PermissionDenied):
        permissions.require("open_device_ad_config")


def test_permission_set_allows_known_agent_action():
    permissions = PermissionSet.for_device_ad_agent()

    assert permissions.require("search_device") == "search_device"


def test_permission_set_denies_explicitly_blocked_action_even_if_allowed():
    permissions = PermissionSet(
        agent_key="test_agent",
        version=1,
        allowed_actions=frozenset({"dangerous_action"}),
        blocked_actions=frozenset({"dangerous_action"}),
    )

    with pytest.raises(PermissionDenied):
        permissions.require("dangerous_action")


def test_approval_payload_hash_is_canonical():
    left = {"ads": [{"name": "May video", "type": "video"}], "device_no": "10086"}
    right = {"device_no": "10086", "ads": [{"type": "video", "name": "May video"}]}

    assert compute_approval_payload_hash(left) == compute_approval_payload_hash(right)


def test_save_approval_passes_when_report_hash_matches():
    report = {
        "device_no": "10086",
        "task_added_ads": [{"name": "May video", "type": "video"}],
        "baseline_ads": [{"name": "Existing image", "type": "image"}],
    }
    approval = TaskApproval(
        id="approval-1",
        task_id="task-1",
        approval_type=ApprovalType.SAVE_APPROVAL,
        subject_type="task",
        subject_id="task-1",
        status=ApprovalStatus.APPROVED,
        requested_payload=build_save_approval_request(report),
    )

    assert verify_save_approval(approval, report) is None


def test_save_approval_rejects_changed_report_after_owner_approval():
    original_report = {"device_no": "10086", "task_added_ads": [{"name": "May video"}]}
    changed_report = {"device_no": "10086", "task_added_ads": [{"name": "Wrong video"}]}
    approval = TaskApproval(
        id="approval-1",
        task_id="task-1",
        approval_type=ApprovalType.SAVE_APPROVAL,
        subject_type="task",
        subject_id="task-1",
        status=ApprovalStatus.APPROVED,
        requested_payload=build_save_approval_request(original_report),
    )

    with pytest.raises(ApprovalGateError, match="hash"):
        verify_save_approval(approval, changed_report)


def test_save_approval_requires_approved_save_approval_record():
    report = {"device_no": "10086", "task_added_ads": [{"name": "May video"}]}
    approval = TaskApproval(
        id="approval-1",
        task_id="task-1",
        approval_type=ApprovalType.CANDIDATE_SELECTION,
        subject_type="task",
        subject_id="task-1",
        status=ApprovalStatus.PENDING,
        requested_payload=build_save_approval_request(report),
    )

    with pytest.raises(ApprovalGateError):
        verify_save_approval(approval, report)
