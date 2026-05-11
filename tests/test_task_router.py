from backend.app.agents.router import RouteKind, TaskRouter


def test_routes_device_binding_command():
    route = TaskRouter().route("给设备 10086 添加五一广告")

    assert route.kind == RouteKind.DEVICE_AD_BINDING
    assert route.agent_key == "device_ad_agent"
    assert route.workflow_key == "device_ad_binding"
    assert route.target_device_no == "10086"


def test_routes_ad_upload_command():
    route = TaskRouter().route("给企业A的春节标签上传 a.mp4 和 b.jpg")

    assert route.kind == RouteKind.AD_UPLOAD
    assert route.agent_key == "ad_upload_agent"
    assert route.workflow_key == "advertisement_upload"
    assert route.company_query == "企业A"
    assert route.tag_query == "春节"
    assert route.upload_asset_queries == ["a.mp4", "b.jpg"]


def test_routes_mixed_command_as_two_phase_plan():
    route = TaskRouter().route("上传五一广告并绑定到设备 10086")

    assert route.kind == RouteKind.MIXED_UPLOAD_THEN_BIND
    assert route.phases == [RouteKind.AD_UPLOAD, RouteKind.DEVICE_AD_BINDING]
    assert route.target_device_no == "10086"


def test_missing_device_number_routes_to_clarification():
    route = TaskRouter().route("给设备添加五一广告")

    assert route.kind == RouteKind.NEEDS_CLARIFICATION
    assert route.missing_fields == ["target_device_no"]


def test_upload_without_company_routes_to_clarification():
    route = TaskRouter().route("上传 a.mp4 和 b.jpg 到春节标签")

    assert route.kind == RouteKind.NEEDS_CLARIFICATION
    assert route.missing_fields == ["company_query"]


def test_unknown_command_routes_to_clarification():
    route = TaskRouter().route("帮我看一下今天任务")

    assert route.kind == RouteKind.NEEDS_CLARIFICATION
    assert route.clarification_reason == "unsupported_intent"
