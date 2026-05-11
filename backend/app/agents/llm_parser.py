from __future__ import annotations

import json
from typing import Any, Protocol

from backend.app.agents.router import CommandParser, DeterministicCommandParser, RouteKind, TaskRoute
from backend.app.core.config import Settings
from backend.app.workflows.state import AdvertisementRequest, AdvertisementType


class LLMParserError(Exception):
    pass


class LLMCommandClient(Protocol):
    def parse_command(self, command: str) -> dict[str, Any]: ...


class OpenAICompatibleCommandClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        temperature: float,
        timeout_seconds: float,
    ) -> None:
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise LLMParserError("LLM parsing requires the openai package.") from exc
        self.model = model
        self.temperature = temperature
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)

    def parse_command(self, command: str) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You parse owner commands for a controlled advertisement automation system. "
                        "Return only JSON with kind, target_device_no, company_query, tag_query, "
                        "upload_asset_queries, requested_ads, missing_fields, and clarification_reason. "
                        "Allowed kind values are device_ad_binding, ad_upload, mixed_upload_then_bind, "
                        "and needs_clarification. Never invent browser actions."
                    ),
                },
                {"role": "user", "content": command},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise LLMParserError("LLM parser returned empty content")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMParserError("LLM parser returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise LLMParserError("LLM parser JSON must be an object")
        return parsed


class LLMCommandParser:
    def __init__(self, *, client: LLMCommandClient) -> None:
        self.client = client

    def parse(self, command: str) -> TaskRoute:
        payload = self.client.parse_command(command)
        return _route_from_payload(command, payload)


class HybridCommandParser:
    def __init__(self, *, deterministic: CommandParser, llm: CommandParser) -> None:
        self.deterministic = deterministic
        self.llm = llm

    def parse(self, command: str) -> TaskRoute:
        route = self.deterministic.parse(command)
        if route.kind != RouteKind.NEEDS_CLARIFICATION:
            return route
        return self.llm.parse(command)


def build_command_parser(settings: Settings, *, llm_client: LLMCommandClient | None = None) -> CommandParser:
    mode = settings.llm_parser_mode.strip().lower()
    if mode in {"", "deterministic", "rules", "rule"}:
        return DeterministicCommandParser()
    llm_parser = LLMCommandParser(client=llm_client or _build_llm_client(settings))
    if mode == "llm":
        return llm_parser
    if mode == "hybrid":
        return HybridCommandParser(deterministic=DeterministicCommandParser(), llm=llm_parser)
    raise LLMParserError(f"Unsupported LLM_PARSER_MODE value: {settings.llm_parser_mode}")


def _build_llm_client(settings: Settings) -> LLMCommandClient:
    provider = settings.llm_provider.strip().lower()
    if provider not in {"openai", "openai_compatible", "openai-compatible"}:
        raise LLMParserError("LLM_PROVIDER must be openai_compatible when LLM parsing is enabled")
    if not settings.llm_api_key.strip():
        raise LLMParserError("LLM_API_KEY is required when LLM parsing is enabled")
    if not settings.llm_model.strip():
        raise LLMParserError("LLM_MODEL is required when LLM parsing is enabled")
    return OpenAICompatibleCommandClient(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        temperature=settings.llm_temperature,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def _route_from_payload(original_command: str, payload: dict[str, Any]) -> TaskRoute:
    try:
        kind = RouteKind(str(payload.get("kind", "")))
    except ValueError as exc:
        raise LLMParserError("LLM parser returned unsupported route kind") from exc

    target_device_no = _optional_string(payload.get("target_device_no"))
    company_query = _optional_string(payload.get("company_query"))
    tag_query = _optional_string(payload.get("tag_query"))
    upload_asset_queries = _string_list(payload.get("upload_asset_queries"))
    requested_ads = _advertisement_requests(payload.get("requested_ads"))
    missing_fields = _string_list(payload.get("missing_fields"))
    clarification_reason = _optional_string(payload.get("clarification_reason"))

    if kind == RouteKind.DEVICE_AD_BINDING:
        if not target_device_no:
            return _clarification(original_command, ["target_device_no"])
        return TaskRoute(
            kind=kind,
            original_command=original_command,
            agent_key="device_ad_agent",
            workflow_key="device_ad_binding",
            target_device_no=target_device_no,
            requested_ads=requested_ads,
        )
    if kind == RouteKind.AD_UPLOAD:
        if not company_query:
            return _clarification(original_command, ["company_query"])
        return TaskRoute(
            kind=kind,
            original_command=original_command,
            agent_key="ad_upload_agent",
            workflow_key="advertisement_upload",
            company_query=company_query,
            tag_query=tag_query,
            upload_asset_queries=upload_asset_queries,
        )
    if kind == RouteKind.MIXED_UPLOAD_THEN_BIND:
        if not target_device_no:
            return _clarification(original_command, ["target_device_no"])
        return TaskRoute(
            kind=kind,
            original_command=original_command,
            target_device_no=target_device_no,
            company_query=company_query,
            tag_query=tag_query,
            upload_asset_queries=upload_asset_queries,
            phases=[RouteKind.AD_UPLOAD, RouteKind.DEVICE_AD_BINDING],
        )
    return TaskRoute(
        kind=RouteKind.NEEDS_CLARIFICATION,
        original_command=original_command,
        missing_fields=missing_fields,
        clarification_reason=clarification_reason or "llm_needs_clarification",
    )


def _clarification(original_command: str, missing_fields: list[str]) -> TaskRoute:
    return TaskRoute(
        kind=RouteKind.NEEDS_CLARIFICATION,
        original_command=original_command,
        missing_fields=missing_fields,
        clarification_reason="missing_required_fields",
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LLMParserError("LLM parser returned a non-string field")
    stripped = value.strip()
    return stripped or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise LLMParserError("LLM parser returned a list field with invalid type")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise LLMParserError("LLM parser returned a list item with invalid type")
        stripped = item.strip()
        if stripped:
            result.append(stripped)
    return result


def _advertisement_requests(value: Any) -> list[AdvertisementRequest]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise LLMParserError("LLM parser returned requested_ads with invalid type")
    requests: list[AdvertisementRequest] = []
    for item in value:
        if not isinstance(item, dict):
            raise LLMParserError("LLM parser returned requested_ads item with invalid type")
        name = _optional_string(item.get("name"))
        if not name:
            continue
        raw_ad_type = _optional_string(item.get("ad_type")) or "unknown"
        try:
            ad_type = AdvertisementType(raw_ad_type)
        except ValueError as exc:
            raise LLMParserError("LLM parser returned unsupported advertisement type") from exc
        requests.append(
            AdvertisementRequest(
                name=name,
                ad_type=ad_type,
                category=_optional_string(item.get("category")),
                notes=_optional_string(item.get("notes")),
            )
        )
    return requests
