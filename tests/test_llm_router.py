import pytest

from backend.app.agents.llm_parser import (
    LLMCommandParser,
    LLMParserError,
    build_command_parser,
)
from backend.app.agents.router import DeterministicCommandParser, RouteKind
from backend.app.browser.mock_admin import MockAdminAdapter
from backend.app.core.config import Settings
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
from backend.app.workflows.state import AdvertisementType


class StubLLMClient:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def parse_command(self, command: str) -> dict[str, object]:
        self.calls.append(command)
        return self.payload


def test_llm_parser_maps_structured_model_output_to_task_route():
    client = StubLLMClient(
        {
            "kind": "ad_upload",
            "company_query": "Company A",
            "tag_query": "Spring",
            "upload_asset_queries": ["a.mp4", "b.jpg"],
        }
    )

    route = LLMCommandParser(client=client).parse("upload these two ad assets")

    assert route.kind == RouteKind.AD_UPLOAD
    assert route.agent_key == "ad_upload_agent"
    assert route.workflow_key == "advertisement_upload"
    assert route.company_query == "Company A"
    assert route.tag_query == "Spring"
    assert route.upload_asset_queries == ["a.mp4", "b.jpg"]
    assert client.calls == ["upload these two ad assets"]


def test_llm_parser_maps_device_binding_ad_requests():
    client = StubLLMClient(
        {
            "kind": "device_ad_binding",
            "target_device_no": "10086",
            "requested_ads": [
                {"name": "May promo video", "ad_type": "video"},
                {"name": "Lobby image", "ad_type": "image", "category": "lobby"},
            ],
        }
    )

    route = LLMCommandParser(client=client).parse("bind these ads to device 10086")

    assert route.kind == RouteKind.DEVICE_AD_BINDING
    assert route.target_device_no == "10086"
    assert [(ad.name, ad.ad_type, ad.category) for ad in route.requested_ads] == [
        ("May promo video", AdvertisementType.VIDEO, None),
        ("Lobby image", AdvertisementType.IMAGE, "lobby"),
    ]


def test_hybrid_parser_uses_deterministic_parser_before_llm():
    client = StubLLMClient({"kind": "needs_clarification", "clarification_reason": "should_not_be_used"})
    parser = build_command_parser(
        Settings(llm_parser_mode="hybrid", llm_provider="openai_compatible", llm_api_key="test", llm_model="test"),
        llm_client=client,
    )

    route = parser.parse("device 10086 bind May promo video")

    assert route.kind == RouteKind.DEVICE_AD_BINDING
    assert route.target_device_no == "10086"
    assert client.calls == []


def test_hybrid_parser_falls_back_to_llm_when_rule_parser_needs_clarification():
    client = StubLLMClient(
        {
            "kind": "device_ad_binding",
            "target_device_no": "10086",
        }
    )
    parser = build_command_parser(
        Settings(llm_parser_mode="hybrid", llm_provider="openai_compatible", llm_api_key="test", llm_model="test"),
        llm_client=client,
    )

    route = parser.parse("put the ad we discussed on screen 10086")

    assert route.kind == RouteKind.DEVICE_AD_BINDING
    assert route.target_device_no == "10086"
    assert client.calls == ["put the ad we discussed on screen 10086"]


def test_llm_parser_requires_model_configuration_when_enabled():
    with pytest.raises(LLMParserError, match="LLM_API_KEY"):
        build_command_parser(Settings(llm_parser_mode="llm", llm_provider="openai_compatible", llm_model="test"))


def test_openai_compatible_parser_can_be_built_from_complete_settings():
    parser = build_command_parser(
        Settings(
            llm_parser_mode="llm",
            llm_provider="openai_compatible",
            llm_api_key="test-key",
            llm_base_url="https://example.test/v1",
            llm_model="test-model",
        )
    )

    assert isinstance(parser, LLMCommandParser)


def test_deterministic_mode_keeps_current_rule_parser_without_llm_configuration():
    parser = build_command_parser(Settings(llm_parser_mode="deterministic"))

    assert isinstance(parser, DeterministicCommandParser)


def test_upload_runner_uses_injected_parser_for_upload_plan(tmp_path):
    client = StubLLMClient(
        {
            "kind": "ad_upload",
            "company_query": "Company A",
            "tag_query": "Spring",
            "upload_asset_queries": ["a.mp4"],
        }
    )
    batch_repo = InMemoryUploadBatchRepository()
    item_repo = InMemoryUploadItemRepository()
    runner = AdvertisementUploadGraphRunner(
        browser=MockAdminAdapter.with_default_fixtures(),
        asset_base_dirs=[tmp_path],
        task_repo=InMemoryTaskRepository(),
        approval_repo=InMemoryApprovalRepository(),
        candidate_repo=InMemoryCandidateRepository(),
        batch_repo=batch_repo,
        item_repo=item_repo,
        asset_candidate_repo=InMemoryLocalAssetCandidateRepository(),
        audit_repo=InMemoryAuditRepository(),
        command_parser=LLMCommandParser(client=client),
    )

    result = runner.create_upload_plan("please upload the video ad I mentioned")

    batch = batch_repo.get_batch(result.batch.id)
    item = item_repo.list_items(batch.id)[0]
    assert batch.company_request == "Company A"
    assert batch.tag_request == "Spring"
    assert item.local_asset_query == "a.mp4"
