import pytest

from backend.app.agents.device_ad_agent import DeviceAdvertisementAgent, DeviceAdWorkflowError
from backend.app.browser.mock_admin import MockAdminAdapter
from backend.app.db.repositories import (
    InMemoryApprovalRepository,
    InMemoryAuditRepository,
    InMemoryCandidateRepository,
    InMemoryTaskRepository,
)
from backend.app.safety.approvals import ApprovalGateError
from backend.app.workflows.state import AdvertisementRequest, AdvertisementType, TaskStatus


def make_agent(adapter: MockAdminAdapter | None = None):
    task_repo = InMemoryTaskRepository()
    approval_repo = InMemoryApprovalRepository()
    candidate_repo = InMemoryCandidateRepository()
    audit_repo = InMemoryAuditRepository()
    agent = DeviceAdvertisementAgent(
        browser=adapter or MockAdminAdapter.with_default_fixtures(),
        task_repo=task_repo,
        approval_repo=approval_repo,
        candidate_repo=candidate_repo,
        audit_repo=audit_repo,
    )
    return agent, task_repo, approval_repo, candidate_repo, audit_repo


def test_device_ad_workflow_prepares_report_then_saves_after_approval():
    agent, task_repo, approval_repo, _, _ = make_agent()

    result = agent.prepare_binding(
        original_command="bind May promo video to device 10086",
        target_device_no="10086",
        requested_ads=[
            AdvertisementRequest(name="May promo video", ad_type=AdvertisementType.VIDEO),
        ],
    )

    task = task_repo.get_task(result.task.id)
    assert task.status == TaskStatus.AWAITING_SAVE_APPROVAL
    assert task.pending_save_report is not None
    assert task.pending_save_report["target_device_no"] == "10086"
    assert [ad.name for ad in task.baseline_ads] == ["Existing lobby image"]
    assert [ad.name for ad in task.task_added_ads] == ["May promo video"]
    assert result.save_approval is not None
    assert approval_repo.get_approval(result.save_approval.id).status.value == "pending"

    saved = agent.approve_and_save(result.task.id, result.save_approval.id, decided_by="owner")

    assert saved.status == TaskStatus.SUCCEEDED
    assert [ad.name for ad in task_repo.get_task(result.task.id).matched_ads] == ["May promo video"]


def test_device_ad_workflow_blocks_save_before_owner_approval():
    agent, _, _, _, _ = make_agent()
    result = agent.prepare_binding(
        original_command="bind May promo video to device 10086",
        target_device_no="10086",
        requested_ads=[
            AdvertisementRequest(name="May promo video", ad_type=AdvertisementType.VIDEO),
        ],
    )

    with pytest.raises(ApprovalGateError):
        agent.save_with_approval(result.task.id, result.save_approval.id)


def test_device_ad_workflow_fails_when_device_not_found():
    agent, task_repo, _, _, _ = make_agent()

    result = agent.prepare_binding(
        original_command="bind May promo video to device 404",
        target_device_no="404",
        requested_ads=[
            AdvertisementRequest(name="May promo video", ad_type=AdvertisementType.VIDEO),
        ],
    )

    task = task_repo.get_task(result.task.id)
    assert task.status == TaskStatus.FAILED
    assert task.error_code == "device_not_found"
    assert result.save_approval is None


def test_device_ad_workflow_waits_for_candidate_selection_when_multiple_ads_match():
    agent, task_repo, _, candidate_repo, _ = make_agent()

    result = agent.prepare_binding(
        original_command="bind May to device 10086",
        target_device_no="10086",
        requested_ads=[AdvertisementRequest(name="May")],
    )

    task = task_repo.get_task(result.task.id)
    candidates = candidate_repo.list_candidates(task.id)
    assert task.status == TaskStatus.AWAITING_CANDIDATE_SELECTION
    assert task.error_code == "multiple_ad_candidates"
    assert sorted(candidate.display_name for candidate in candidates) == [
        "May promo image",
        "May promo video",
    ]
    assert result.save_approval is None


def test_device_ad_workflow_fails_when_advertisement_is_missing():
    agent, task_repo, _, _, _ = make_agent()

    result = agent.prepare_binding(
        original_command="bind Missing campaign to device 10086",
        target_device_no="10086",
        requested_ads=[AdvertisementRequest(name="Missing campaign")],
    )

    task = task_repo.get_task(result.task.id)
    assert task.status == TaskStatus.FAILED
    assert task.error_code == "advertisement_not_found"
    assert result.save_approval is None


class BaselineDroppingAdapter(MockAdminAdapter):
    def read_pending_ads(self):
        return [ad for ad in super().read_pending_ads() if ad.id != "ad-existing-image"]


def test_device_ad_workflow_blocks_save_report_when_baseline_is_missing():
    agent, task_repo, _, _, _ = make_agent(BaselineDroppingAdapter.with_default_fixtures())

    result = agent.prepare_binding(
        original_command="bind May promo video to device 10086",
        target_device_no="10086",
        requested_ads=[
            AdvertisementRequest(name="May promo video", ad_type=AdvertisementType.VIDEO),
        ],
    )

    task = task_repo.get_task(result.task.id)
    assert task.status == TaskStatus.AWAITING_CORRECTION_DECISION
    assert task.error_code == "baseline_ad_missing"
    assert result.save_approval is None


def test_correction_removal_can_only_target_current_task_additions():
    agent, task_repo, _, _, _ = make_agent()
    result = agent.prepare_binding(
        original_command="bind May promo video to device 10086",
        target_device_no="10086",
        requested_ads=[
            AdvertisementRequest(name="May promo video", ad_type=AdvertisementType.VIDEO),
        ],
    )
    task = task_repo.get_task(result.task.id)

    assert agent.validate_correction_removal(task.id, ["ad-may-video"]) == ["ad-may-video"]
    with pytest.raises(DeviceAdWorkflowError, match="baseline"):
        agent.validate_correction_removal(task.id, ["ad-existing-image"])
