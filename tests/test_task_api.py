from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_task_api_creates_device_binding_task_and_approves_save():
    client = TestClient(create_app())

    created = client.post("/tasks", json={"command": "给设备 10086 添加 May promo video"})

    assert created.status_code == 200
    body = created.json()
    assert body["task"]["status"] == "awaiting_save_approval"
    approval_id = body["approvals"][0]["id"]

    approved = client.post(f"/tasks/{body['task']['id']}/approvals/{approval_id}/approve", json={"decided_by": "owner"})

    assert approved.status_code == 200
    assert approved.json()["task"]["status"] == "succeeded"


def test_task_api_gets_status_and_events():
    client = TestClient(create_app())
    created = client.post("/tasks", json={"command": "给设备 10086 添加 May promo video"}).json()

    status = client.get(f"/tasks/{created['task']['id']}")
    events = client.get(f"/tasks/{created['task']['id']}/events")

    assert status.status_code == 200
    assert status.json()["task"]["id"] == created["task"]["id"]
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()["events"]]


def test_task_api_selects_candidate():
    client = TestClient(create_app())
    created = client.post("/tasks", json={"command": "给设备 10086 添加 May"}).json()
    candidate_id = created["candidates"][0]["id"]

    selected = client.post(
        f"/tasks/{created['task']['id']}/candidates/{candidate_id}/select",
        json={"selected_by": "owner"},
    )

    assert selected.status_code == 200
    assert selected.json()["candidates"][0]["selection_status"] == "selected"


def test_task_api_confirms_upload_plan_and_approves_item_save(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    client = TestClient(create_app(asset_base_dirs=[tmp_path]))
    created = client.post("/tasks", json={"command": "给企业A的Existing标签上传 a.mp4"}).json()
    plan_approval_id = created["approvals"][0]["id"]

    planned = client.post(
        f"/tasks/{created['task']['id']}/approvals/{plan_approval_id}/approve",
        json={"decided_by": "owner"},
    )
    item_approval_id = [
        approval for approval in planned.json()["approvals"] if approval["subject_type"] == "upload_item"
    ][0]["id"]
    saved = client.post(
        f"/tasks/{created['task']['id']}/approvals/{item_approval_id}/approve",
        json={"decided_by": "owner"},
    )

    assert planned.status_code == 200
    assert planned.json()["task"]["status"] == "awaiting_item_save_approval"
    assert saved.status_code == 200
    assert saved.json()["task"]["status"] == "succeeded"
    assert saved.json()["upload_items"][0]["status"] == "saved"


def test_task_api_approves_missing_tag_creation(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    client = TestClient(create_app(asset_base_dirs=[tmp_path]))
    created = client.post("/tasks", json={"command": "给企业A的Spring标签上传 a.mp4"}).json()
    plan_approval_id = created["approvals"][0]["id"]
    waiting_for_tag = client.post(
        f"/tasks/{created['task']['id']}/approvals/{plan_approval_id}/approve",
        json={"decided_by": "owner"},
    ).json()
    tag_approval_id = [
        approval for approval in waiting_for_tag["approvals"] if approval["subject_type"] == "upload_batch"
    ][-1]["id"]

    continued = client.post(
        f"/tasks/{created['task']['id']}/approvals/{tag_approval_id}/approve",
        json={"decided_by": "owner"},
    )

    assert waiting_for_tag["task"]["status"] == "awaiting_tag_creation_confirmation"
    assert continued.status_code == 200
    assert continued.json()["task"]["status"] == "awaiting_item_save_approval"


def test_task_api_rejects_approval():
    client = TestClient(create_app())
    created = client.post("/tasks", json={"command": "给设备 10086 添加 May promo video"}).json()
    approval_id = created["approvals"][0]["id"]

    rejected = client.post(
        f"/tasks/{created['task']['id']}/approvals/{approval_id}/reject",
        json={"decided_by": "owner", "reason": "wrong ad"},
    )

    assert rejected.status_code == 200
    assert rejected.json()["approvals"][0]["status"] == "rejected"
