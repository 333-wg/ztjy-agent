import pytest

from backend.app.db.repositories import (
    InMemoryApprovalRepository,
    InMemoryAuditRepository,
    InMemoryCandidateRepository,
    InMemoryLocalAssetCandidateRepository,
    InMemoryTaskRepository,
    InMemoryUploadBatchRepository,
    InMemoryUploadItemRepository,
)
from backend.app.db.supabase import SupabaseSettings, create_server_supabase_client
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
        original_command="bind May campaign to device 10086",
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


def test_approval_repository_defaults_to_task_subject():
    repo = InMemoryApprovalRepository()

    approval = repo.create_approval(
        task_id="task-1",
        approval_type=ApprovalType.SAVE_APPROVAL,
    )

    assert approval.subject_type == "task"
    assert approval.subject_id == "task-1"


def test_approval_repository_accepts_specific_subject():
    repo = InMemoryApprovalRepository()

    approval = repo.create_approval(
        task_id="task-1",
        approval_type=ApprovalType.CANDIDATE_SELECTION,
        subject_type="candidate",
        subject_id="candidate-1",
    )

    assert approval.subject_type == "candidate"
    assert approval.subject_id == "candidate-1"


def test_approval_types_match_current_database_constraint():
    assert {approval_type.value for approval_type in ApprovalType} == {
        "command_confirmation",
        "login_complete",
        "candidate_selection",
        "save_approval",
    }


def test_approval_repository_copies_mutable_payloads_on_create_and_decision():
    repo = InMemoryApprovalRepository()
    requested_payload = {"items": ["before"]}
    decision_payload = {"confirmed": {"value": True}}

    approval = repo.create_approval(
        task_id="task-1",
        approval_type=ApprovalType.COMMAND_CONFIRMATION,
        requested_payload=requested_payload,
    )
    repo.record_decision(
        approval.id,
        ApprovalStatus.APPROVED,
        decision_payload=decision_payload,
    )
    requested_payload["items"].append("after")
    decision_payload["confirmed"]["value"] = False

    saved = repo.get_approval(approval.id)
    assert saved.requested_payload == {"items": ["before"]}
    assert saved.decision_payload == {"confirmed": {"value": True}}


def test_upload_repositories_copy_mutable_create_and_update_payloads():
    batches = InMemoryUploadBatchRepository()
    items = InMemoryUploadItemRepository()
    created_tag = {"name": "launch", "labels": ["new"]}
    selected_asset_metadata = {"duration": {"seconds": 10}}

    batch = batches.create_batch(
        task_id="task-1",
        company_request="Company A",
        total_items=1,
        created_tag=created_tag,
    )
    item = items.create_item(
        task_id="task-1",
        batch_id=batch.id,
        item_order=1,
        requested_name="May video",
        requested_type=AdvertisementType.VIDEO,
        selected_asset_metadata=selected_asset_metadata,
    )
    matched_company = {"name": "Company A", "aliases": ["primary"]}
    form_payload = {"fields": {"title": "May video"}}

    batches.update_batch(batch.id, matched_company=matched_company)
    items.update_item(item.id, form_payload=form_payload)
    created_tag["labels"].append("mutated")
    selected_asset_metadata["duration"]["seconds"] = 20
    matched_company["aliases"].append("mutated")
    form_payload["fields"]["title"] = "changed"

    saved_batch = batches.get_batch(batch.id)
    saved_item = items.get_item(item.id)
    assert saved_batch.created_tag == {"name": "launch", "labels": ["new"]}
    assert saved_batch.matched_company == {"name": "Company A", "aliases": ["primary"]}
    assert saved_item.selected_asset_metadata == {"duration": {"seconds": 10}}
    assert saved_item.form_payload == {"fields": {"title": "May video"}}


def test_candidate_and_asset_repositories_copy_mutable_create_payloads():
    candidates = InMemoryCandidateRepository()
    assets = InMemoryLocalAssetCandidateRepository()
    candidate_metadata = {"labels": ["campaign"]}
    asset_metadata = {"dimensions": {"width": 1080}}

    candidate = candidates.create_candidate(
        task_id="task-1",
        candidate_type="advertisement",
        display_name="May campaign",
        metadata=candidate_metadata,
    )
    asset = assets.create_candidate(
        task_id="task-1",
        upload_item_id="item-1",
        file_name="may.jpg",
        local_path_ref="D:/ads/may.jpg",
        metadata=asset_metadata,
    )
    candidate_metadata["labels"].append("mutated")
    asset_metadata["dimensions"]["width"] = 1920

    assert candidates.get_candidate(candidate.id).metadata == {"labels": ["campaign"]}
    assert assets.get_candidate(asset.id).metadata == {"dimensions": {"width": 1080}}


def test_audit_repository_copies_mutable_details_on_create():
    repo = InMemoryAuditRepository()
    details = {"steps": ["opened device list"]}

    event = repo.record_event(
        task_id="task-1",
        event_type="step_completed",
        summary="step completed",
        details=details,
    )
    details["steps"].append("mutated")

    saved = repo.list_events("task-1")[0]
    assert saved.id == event.id
    assert saved.details == {"steps": ["opened device list"]}


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
        company_request="Company A",
        tag_request="May campaign",
        total_items=1,
    )
    item = items.create_item(
        task_id="task-1",
        batch_id=batch.id,
        item_order=1,
        requested_name="May video",
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
        display_name="May campaign",
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


def test_server_supabase_client_requires_service_role_key():
    settings = SupabaseSettings(
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
        supabase_service_role_key="",
    )

    with pytest.raises(ValueError, match="server Supabase key"):
        create_server_supabase_client(settings)
