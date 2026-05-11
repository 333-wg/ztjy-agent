from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_e2e_device_binding_mock_scenario():
    client = TestClient(create_app())

    created = client.post("/tasks", json={"command": "给设备 10086 添加 May promo video"}).json()
    approval_id = created["approvals"][0]["id"]
    saved = client.post(
        f"/tasks/{created['task']['id']}/approvals/{approval_id}/approve",
        json={"decided_by": "owner"},
    ).json()
    events = client.get(f"/tasks/{created['task']['id']}/events").json()["events"]

    assert saved["task"]["status"] == "succeeded"
    assert "save_succeeded" in {event["event_type"] for event in events}


def test_e2e_advertisement_upload_mock_scenario(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    (tmp_path / "b.jpg").write_bytes(b"image")
    client = TestClient(create_app(asset_base_dirs=[tmp_path]))

    created = client.post("/tasks", json={"command": "给企业A的Existing标签上传 a.mp4 b.jpg"}).json()
    plan_approval = created["approvals"][0]
    first_ready = client.post(
        f"/tasks/{created['task']['id']}/approvals/{plan_approval['id']}/approve",
        json={"decided_by": "owner"},
    ).json()
    first_item_approval = [
        approval for approval in first_ready["approvals"] if approval["subject_type"] == "upload_item"
    ][0]
    second_ready = client.post(
        f"/tasks/{created['task']['id']}/approvals/{first_item_approval['id']}/approve",
        json={"decided_by": "owner"},
    ).json()
    second_item_approval = [
        approval
        for approval in second_ready["approvals"]
        if approval["subject_type"] == "upload_item" and approval["status"] == "pending"
    ][0]
    completed = client.post(
        f"/tasks/{created['task']['id']}/approvals/{second_item_approval['id']}/approve",
        json={"decided_by": "owner"},
    ).json()

    assert completed["task"]["status"] == "succeeded"
    assert [item["status"] for item in completed["upload_items"]] == ["saved", "saved"]


def test_e2e_mixed_upload_then_bind_requires_separate_handoff_confirmation(tmp_path):
    (tmp_path / "a.mp4").write_bytes(b"video")
    client = TestClient(create_app(asset_base_dirs=[tmp_path]))

    created = client.post(
        "/tasks",
        json={"command": "给企业A的Existing标签上传 a.mp4 并绑定到设备 10086"},
    ).json()
    plan_approval = created["approvals"][0]
    ready = client.post(
        f"/tasks/{created['task']['id']}/approvals/{plan_approval['id']}/approve",
        json={"decided_by": "owner"},
    ).json()
    item_approval = [
        approval for approval in ready["approvals"] if approval["subject_type"] == "upload_item"
    ][0]
    completed = client.post(
        f"/tasks/{created['task']['id']}/approvals/{item_approval['id']}/approve",
        json={"decided_by": "owner"},
    ).json()

    assert completed["task"]["status"] == "awaiting_command_confirmation"
    assert completed["task"]["awaiting_action"] == "owner_device_binding_handoff_confirmation"
    assert completed["task"]["parsed_command"]["handoff"]["target_device_no"] == "10086"
    assert any(
        approval["subject_type"] == "task" and approval["approval_type"] == "command_confirmation"
        for approval in completed["approvals"]
    )
