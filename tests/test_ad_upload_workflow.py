import pytest

from backend.app.agents.ad_upload_agent import AdvertisementUploadAgent
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
    AdvertisementType,
    ApprovalStatus,
    TaskStatus,
    UploadItemStatus,
)


def make_agent(tmp_path, adapter: MockAdminAdapter | None = None):
    task_repo = InMemoryTaskRepository()
    approval_repo = InMemoryApprovalRepository()
    candidate_repo = InMemoryCandidateRepository()
    batch_repo = InMemoryUploadBatchRepository()
    item_repo = InMemoryUploadItemRepository()
    asset_candidate_repo = InMemoryLocalAssetCandidateRepository()
    audit_repo = InMemoryAuditRepository()
    agent = AdvertisementUploadAgent(
        browser=adapter or MockAdminAdapter.with_default_fixtures(),
        asset_base_dirs=[tmp_path],
        task_repo=task_repo,
        approval_repo=approval_repo,
        candidate_repo=candidate_repo,
        batch_repo=batch_repo,
        item_repo=item_repo,
        asset_candidate_repo=asset_candidate_repo,
        audit_repo=audit_repo,
    )
    return agent, task_repo, approval_repo, batch_repo, item_repo


def test_upload_plan_parses_company_tag_and_multiple_items(tmp_path):
    agent, task_repo, approval_repo, batch_repo, item_repo = make_agent(tmp_path)

    result = agent.create_upload_plan(
        "给企业A的Spring标签上传 a.mp4 b.mp4 c.jpg",
    )

    task = task_repo.get_task(result.task.id)
    batch = batch_repo.get_batch(result.batch.id)
    items = item_repo.list_items(batch.id)
    assert task.status == TaskStatus.AWAITING_UPLOAD_PLAN_CONFIRMATION
    assert batch.company_request == "Company A"
    assert batch.tag_request == "Spring"
    assert [(item.requested_type, item.local_asset_query) for item in items] == [
        (AdvertisementType.VIDEO, "a.mp4"),
        (AdvertisementType.VIDEO, "b.mp4"),
        (AdvertisementType.IMAGE, "c.jpg"),
    ]
    assert approval_repo.get_approval(result.plan_approval.id).status == ApprovalStatus.PENDING


def test_upload_workflow_processes_only_one_item_until_item_approval(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    (tmp_path / "b.jpg").write_bytes(b"image")
    agent, _, _, batch_repo, item_repo = make_agent(tmp_path)
    plan = agent.create_upload_plan("给企业A的Existing标签上传 a.mp4 b.jpg")

    started = agent.approve_plan_and_start(plan.task.id, plan.plan_approval.id, decided_by="owner")
    batch = batch_repo.get_batch(started.batch.id)
    items = item_repo.list_items(batch.id)

    active_items = [
        item
        for item in items
        if item.status in {UploadItemStatus.UPLOADING, UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL}
    ]
    assert len(active_items) == 1
    assert active_items[0].item_order == 1
    assert items[1].status == UploadItemStatus.PENDING


def test_missing_tag_requires_owner_approval_before_creation(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    agent, task_repo, approval_repo, batch_repo, _ = make_agent(tmp_path)
    plan = agent.create_upload_plan("给企业A的Spring标签上传 a.mp4")

    started = agent.approve_plan_and_start(plan.task.id, plan.plan_approval.id, decided_by="owner")
    task = task_repo.get_task(started.task.id)
    batch = batch_repo.get_batch(started.batch.id)

    assert task.status == TaskStatus.AWAITING_TAG_CREATION_CONFIRMATION
    assert batch.created_tag is None
    assert started.tag_creation_approval is not None
    assert approval_repo.get_approval(started.tag_creation_approval.id).status == ApprovalStatus.PENDING

    resumed = agent.approve_tag_creation_and_continue(
        started.task.id,
        started.tag_creation_approval.id,
        decided_by="owner",
    )

    assert batch_repo.get_batch(batch.id).created_tag["name"] == "Spring"
    assert item_repo_statuses(resumed.batch.id, agent) == [UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL]


def test_item_approval_saves_only_that_item_and_then_prepares_next(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    (tmp_path / "b.jpg").write_bytes(b"image")
    agent, _, approval_repo, batch_repo, item_repo = make_agent(tmp_path)
    plan = agent.create_upload_plan("给企业A的Existing标签上传 a.mp4 b.jpg")
    started = agent.approve_plan_and_start(plan.task.id, plan.plan_approval.id, decided_by="owner")
    first_approval = started.item_save_approval

    after_first = agent.approve_item_and_continue(started.task.id, first_approval.id, decided_by="owner")
    items = item_repo.list_items(after_first.batch.id)

    assert items[0].status == UploadItemStatus.SAVED
    assert items[1].status == UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL
    assert approval_repo.get_approval(first_approval.id).status == ApprovalStatus.APPROVED
    assert after_first.item_save_approval.subject_id == items[1].id


def test_one_item_approval_never_saves_another_item(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    (tmp_path / "b.jpg").write_bytes(b"image")
    agent, _, _, _, item_repo = make_agent(tmp_path)
    plan = agent.create_upload_plan("给企业A的Existing标签上传 a.mp4 b.jpg")
    started = agent.approve_plan_and_start(plan.task.id, plan.plan_approval.id, decided_by="owner")

    with pytest.raises(ValueError, match="does not authorize current item"):
        agent.save_item_with_approval(started.task.id, item_repo.list_items(started.batch.id)[1].id, started.item_save_approval.id)


def test_failed_item_can_change_asset_and_retry_current_item(tmp_path):
    agent, task_repo, _, _, item_repo = make_agent(tmp_path)
    plan = agent.create_upload_plan("给企业A的Existing标签上传 missing.mp4")
    started = agent.approve_plan_and_start(plan.task.id, plan.plan_approval.id, decided_by="owner")
    item = item_repo.list_items(started.batch.id)[0]
    assert item.status == UploadItemStatus.FAILED
    assert task_repo.get_task(started.task.id).status == TaskStatus.FAILED

    (tmp_path / "replacement.mp4").write_bytes(b"video")
    retried = agent.change_item_asset_and_retry(started.task.id, item.id, "replacement.mp4")
    retried_item = item_repo.get_item(item.id)

    assert retried_item.status == UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL
    assert retried_item.local_asset_query == "replacement.mp4"
    assert retried.item_save_approval.subject_id == item.id


def test_retry_current_item_reprocesses_pending_item(tmp_path):
    agent, _, _, _, item_repo = make_agent(tmp_path)
    plan = agent.create_upload_plan("给企业A的Existing标签上传 missing.mp4")
    started = agent.approve_plan_and_start(plan.task.id, plan.plan_approval.id, decided_by="owner")
    item = item_repo.list_items(started.batch.id)[0]

    (tmp_path / "missing.mp4").write_bytes(b"video")
    retried = agent.retry_current_item(started.task.id, item.id)

    assert item_repo.get_item(item.id).status == UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL
    assert retried.item_save_approval.subject_id == item.id


def test_skip_cancel_and_manual_takeover_decisions_are_supported(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    (tmp_path / "b.jpg").write_bytes(b"image")
    agent, task_repo, _, batch_repo, item_repo = make_agent(tmp_path)
    plan = agent.create_upload_plan("给企业A的Existing标签上传 a.mp4 b.jpg")
    started = agent.approve_plan_and_start(plan.task.id, plan.plan_approval.id, decided_by="owner")
    first_item, second_item = item_repo.list_items(started.batch.id)

    after_skip = agent.skip_item_and_continue(started.task.id, first_item.id)
    assert item_repo.get_item(first_item.id).status == UploadItemStatus.SKIPPED
    assert item_repo.get_item(second_item.id).status == UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL
    assert after_skip.item_save_approval.subject_id == second_item.id

    cancelled = agent.cancel_remaining_items(started.task.id)
    assert task_repo.get_task(started.task.id).status == TaskStatus.CANCELLED
    assert batch_repo.get_batch(cancelled.batch.id).status == "cancelled"

    manual = agent.manual_takeover(started.task.id)
    assert manual.task.awaiting_action == "manual_takeover"
    assert batch_repo.get_batch(manual.batch.id).status == "manual_takeover"


def item_repo_statuses(batch_id: str, agent: AdvertisementUploadAgent):
    return [item.status for item in agent.item_repo.list_items(batch_id)]
