from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class RouteKind(StrEnum):
    DEVICE_AD_BINDING = "device_ad_binding"
    AD_UPLOAD = "ad_upload"
    MIXED_UPLOAD_THEN_BIND = "mixed_upload_then_bind"
    NEEDS_CLARIFICATION = "needs_clarification"


@dataclass(frozen=True)
class TaskRoute:
    kind: RouteKind
    original_command: str
    agent_key: str | None = None
    workflow_key: str | None = None
    target_device_no: str | None = None
    company_query: str | None = None
    tag_query: str | None = None
    upload_asset_queries: list[str] = field(default_factory=list)
    phases: list[RouteKind] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    clarification_reason: str | None = None


class CommandParser(Protocol):
    def parse(self, command: str) -> TaskRoute: ...


class DeterministicCommandParser:
    _file_pattern = re.compile(r"[\w.-]+\.(?:mp4|mov|avi|mkv|jpg|jpeg|png|webp)", re.IGNORECASE)
    _device_patterns = (
        re.compile(r"设备(?:号|编号)?\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9_-]*)"),
        re.compile(r"device(?:\s*(?:no|number))?\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9_-]*)", re.IGNORECASE),
    )
    _company_patterns = (
        re.compile(r"企业\s*([^\s的,，。]+)"),
        re.compile(r"company\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9 _-]*)", re.IGNORECASE),
    )
    _tag_patterns = (
        re.compile(r"的\s*([A-Za-z0-9_\-\u4e00-\u9fff]+)\s*标签"),
        re.compile(r"到\s*([A-Za-z0-9_\-\u4e00-\u9fff]+)\s*标签"),
        re.compile(r"tag\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9 _-]*)", re.IGNORECASE),
    )

    def parse(self, command: str) -> TaskRoute:
        normalized = " ".join(command.strip().split())
        target_device_no = self._extract_device_no(normalized)
        company_query = self._extract_company_query(normalized)
        tag_query = self._extract_tag_query(normalized)
        upload_asset_queries = self._extract_upload_asset_queries(normalized)

        has_device_intent = self._has_device_intent(normalized)
        has_upload_intent = self._has_upload_intent(normalized, upload_asset_queries)
        has_binding_intent = self._has_binding_intent(normalized)

        if has_upload_intent and has_device_intent and has_binding_intent:
            if not target_device_no:
                return self._clarification(normalized, ["target_device_no"])
            return TaskRoute(
                kind=RouteKind.MIXED_UPLOAD_THEN_BIND,
                original_command=normalized,
                target_device_no=target_device_no,
                company_query=company_query,
                tag_query=tag_query,
                upload_asset_queries=upload_asset_queries,
                phases=[RouteKind.AD_UPLOAD, RouteKind.DEVICE_AD_BINDING],
            )

        if has_device_intent:
            if not target_device_no:
                return self._clarification(normalized, ["target_device_no"])
            return TaskRoute(
                kind=RouteKind.DEVICE_AD_BINDING,
                original_command=normalized,
                agent_key="device_ad_agent",
                workflow_key="device_ad_binding",
                target_device_no=target_device_no,
            )

        if has_upload_intent:
            if not company_query:
                return self._clarification(normalized, ["company_query"])
            return TaskRoute(
                kind=RouteKind.AD_UPLOAD,
                original_command=normalized,
                agent_key="ad_upload_agent",
                workflow_key="advertisement_upload",
                company_query=company_query,
                tag_query=tag_query,
                upload_asset_queries=upload_asset_queries,
            )

        return TaskRoute(
            kind=RouteKind.NEEDS_CLARIFICATION,
            original_command=normalized,
            clarification_reason="unsupported_intent",
        )

    def _extract_device_no(self, command: str) -> str | None:
        for pattern in self._device_patterns:
            match = pattern.search(command)
            if match:
                return match.group(1)
        return None

    def _extract_company_query(self, command: str) -> str | None:
        match = self._company_patterns[0].search(command)
        if match:
            return f"企业{match.group(1)}"
        match = self._company_patterns[1].search(command)
        if match:
            return f"Company {match.group(1).strip()}"
        return None

    def _extract_tag_query(self, command: str) -> str | None:
        for pattern in self._tag_patterns:
            match = pattern.search(command)
            if match:
                return match.group(1).strip()
        return None

    def _extract_upload_asset_queries(self, command: str) -> list[str]:
        return [match.group(0) for match in self._file_pattern.finditer(command)]

    def _has_device_intent(self, command: str) -> bool:
        lowered = command.lower()
        return "设备" in command or "device" in lowered

    def _has_upload_intent(self, command: str, upload_asset_queries: list[str]) -> bool:
        lowered = command.lower()
        return "上传" in command or "upload" in lowered or bool(upload_asset_queries)

    def _has_binding_intent(self, command: str) -> bool:
        lowered = command.lower()
        return any(token in command for token in ("绑定", "添加", "投放", "下发")) or "bind" in lowered

    def _clarification(self, command: str, missing_fields: list[str]) -> TaskRoute:
        return TaskRoute(
            kind=RouteKind.NEEDS_CLARIFICATION,
            original_command=command,
            missing_fields=missing_fields,
            clarification_reason="missing_required_fields",
        )


class TaskRouter:
    def __init__(self, parser: CommandParser | None = None) -> None:
        self._parser = parser or DeterministicCommandParser()

    def route(self, command: str) -> TaskRoute:
        return self._parser.parse(command)
