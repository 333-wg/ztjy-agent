from backend.app.db.repositories import (
    InMemoryApprovalRepository,
    InMemoryAuditRepository,
    InMemoryCandidateRepository,
    InMemoryLocalAssetCandidateRepository,
    InMemoryTaskRepository,
    InMemoryUploadBatchRepository,
    InMemoryUploadItemRepository,
)
from backend.app.db.supabase import SupabaseSettings
from backend.app.workflows.state import (
    AdvertisementType,
    ApprovalStatus,
    ApprovalType,
    TaskStatus,
    UploadItemStatus,
)


def test_task_repository_persists_status_update():
    repo = InMemoryTaskRepository()
    task = repo.create_task(
        original_command="给设备 10086 添加五一广告",
        agent_key="device_ad_agent",
        workflow_key="device_ad_binding",
    )

    repo.update_task_status(task.id, TaskStatus.AWAITING_COMMAND_CONFIRMATION)

    assert repo.get_task(task.id).status == TaskStatus.AWAITING_COMMAND_CONFIRMATION


def test_approval_repository_records_decision():
    repo = InMemoryApprovalRepository()
    approval = repo.create_approval(
        task_id="task-1",
        approval_type=ApprovalType.COMMAND_CONFIRMATION,
        requested_payload={"device_no": "10086"},
    )

    repo.record_decision(
        approval.id,
        ApprovalStatus.APPROVED,
        decision_payload={"confirmed": True},
        decided_by="owner",
    )

    saved = repo.get_approval(approval.id)
    assert saved.status == ApprovalStatus.APPROVED
    assert saved.decision_payload == {"confirmed": True}
    assert saved.decided_by == "owner"
    assert saved.decided_at is not None


def test_audit_repository_lists_events_for_task_in_order():
    repo = InMemoryAuditRepository()

    first = repo.record_event(task_id="task-1", event_type="task_created", summary="created")
    second = repo.record_event(task_id="task-1", event_type="status_changed", summary="running")
    repo.record_event(task_id="task-2", event_type="task_created", summary="other")

    assert repo.list_events("task-1") == [first, second]


def test_upload_repositories_persist_batch_and_item_statuses():
    batches = InMemoryUploadBatchRepository()
    items = InMemoryUploadItemRepository()

    batch = batches.create_batch(
        task_id="task-1",
        company_request="企业A",
        tag_request="五一活动",
        total_items=1,
    )
    item = items.create_item(
        task_id="task-1",
        batch_id=batch.id,
        item_order=1,
        requested_name="五一视频",
        requested_type=AdvertisementType.VIDEO,
        local_asset_query="may.mp4",
    )

    batches.update_batch(batch.id, status="running", completed_items=0)
    items.update_item(item.id, status=UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL)

    assert batches.get_batch(batch.id).status == "running"
    assert items.get_item(item.id).status == UploadItemStatus.AWAITING_ITEM_SAVE_APPROVAL
    assert items.list_items(batch.id) == [items.get_item(item.id)]


def test_candidate_and_local_asset_repositories_persist_selection():
    candidates = InMemoryCandidateRepository()
    assets = InMemoryLocalAssetCandidateRepository()

    candidate = candidates.create_candidate(
        task_id="task-1",
        candidate_type="advertisement",
        display_name="五一广告",
        external_ref="ad-1",
    )
    asset = assets.create_candidate(
        task_id="task-1",
        upload_item_id="item-1",
        file_name="may.jpg",
        local_path_ref="D:/ads/may.jpg",
        media_type=AdvertisementType.IMAGE,
    )

    candidates.select_candidate(candidate.id, selected_by="owner")
    assets.select_candidate(asset.id, selected_by="owner")

    assert candidates.get_candidate(candidate.id).selection_status == "selected"
    assert assets.get_candidate(asset.id).selection_status == "selected"


def test_supabase_settings_keep_service_role_server_side_only():
    settings = SupabaseSettings(
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
        supabase_service_role_key="service-key",
    )

    public_config = settings.public_config()

    assert public_config == {
        "supabase_url": "https://example.supabase.co",
        "supabase_anon_key": "anon-key",
    }
    assert "service-key" not in str(public_config)
