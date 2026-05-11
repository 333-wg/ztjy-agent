import pytest
from langgraph.checkpoint.memory import InMemorySaver

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
from backend.app.workflows.ad_upload_graph import AdvertisementUploadGraphRunner
from backend.app.workflows.checkpointing import (
    create_checkpointer_resource,
    device_ad_thread_id,
    graph_thread_config,
    upload_item_thread_id,
)
from backend.app.workflows.device_ad_graph import DeviceAdGraphRunner
from backend.app.workflows.state import AdvertisementRequest, AdvertisementType


def test_memory_checkpointer_resource_is_enabled_for_local_workflows():
    resource = create_checkpointer_resource("memory")

    assert isinstance(resource.checkpointer, InMemorySaver)


def test_postgres_checkpointer_requires_a_connection_string():
    with pytest.raises(ValueError, match="LANGGRAPH_POSTGRES_URL"):
        create_checkpointer_resource("postgres", postgres_url="")


def test_device_graph_persists_state_with_task_thread_id():
    checkpointer = InMemorySaver()
    task_repo = InMemoryTaskRepository()
    runner = DeviceAdGraphRunner(
        browser=MockAdminAdapter.with_default_fixtures(),
        task_repo=task_repo,
        approval_repo=InMemoryApprovalRepository(),
        candidate_repo=InMemoryCandidateRepository(),
        audit_repo=InMemoryAuditRepository(),
        checkpointer=checkpointer,
    )

    result = runner.prepare(
        original_command="bind May promo video to device 10086",
        target_device_no="10086",
        requested_ads=[AdvertisementRequest(name="May promo video", ad_type=AdvertisementType.VIDEO)],
    )

    snapshot = runner.graph.get_state(graph_thread_config(device_ad_thread_id(result.task.id)))
    assert snapshot.values["task_id"] == result.task.id
    assert snapshot.values["target_device_no"] == "10086"
    assert snapshot.values["save_approval"].id == result.save_approval.id


def test_upload_item_graph_persists_state_with_item_thread_id(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    checkpointer = InMemorySaver()
    task_repo = InMemoryTaskRepository()
    batch_repo = InMemoryUploadBatchRepository()
    item_repo = InMemoryUploadItemRepository()
    runner = AdvertisementUploadGraphRunner(
        browser=MockAdminAdapter.with_default_fixtures(),
        asset_base_dirs=[tmp_path],
        task_repo=task_repo,
        approval_repo=InMemoryApprovalRepository(),
        candidate_repo=InMemoryCandidateRepository(),
        batch_repo=batch_repo,
        item_repo=item_repo,
        asset_candidate_repo=InMemoryLocalAssetCandidateRepository(),
        audit_repo=InMemoryAuditRepository(),
        checkpointer=checkpointer,
    )
    plan = runner.create_upload_plan("给企业A的Existing标签上传 a.mp4")

    started = runner.approve_plan_and_start(plan.task.id, plan.plan_approval.id, decided_by="owner")
    item = item_repo.list_items(started.batch.id)[0]

    snapshot = runner.item_graph.get_state(graph_thread_config(upload_item_thread_id(started.task.id, item.id)))
    assert snapshot.values["task_id"] == started.task.id
    assert snapshot.values["batch_id"] == started.batch.id
    assert snapshot.values["item_id"] == item.id
    assert snapshot.values["item_save_approval"].subject_id == item.id
