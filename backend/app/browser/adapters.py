from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.app.workflows.state import AdvertisementType


class BrowserOperationError(Exception):
    """Raised when a guarded browser operation cannot be completed safely."""


@dataclass(frozen=True)
class LoginState:
    logged_in: bool
    reason: str | None = None


@dataclass(frozen=True)
class DeviceRecord:
    id: str
    device_no: str
    display_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdvertisementRecord:
    id: str
    name: str
    ad_type: AdvertisementType
    category: str | None = None
    local_path_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CompanyRecord:
    id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TagRecord:
    id: str
    company_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SaveResult:
    succeeded: bool
    saved_ids: list[str] = field(default_factory=list)
    saved_ad: AdvertisementRecord | None = None
    message: str | None = None


class DeviceAdBrowserAdapter(Protocol):
    def check_login(self) -> LoginState: ...

    def open_device_management(self) -> None: ...

    def search_device(self, device_no: str) -> list[DeviceRecord]: ...

    def open_device_ad_config(self, device_id: str) -> None: ...

    def read_existing_device_ads(self) -> list[AdvertisementRecord]: ...

    def search_ads(
        self,
        name: str,
        ad_type: AdvertisementType | None = None,
        category: str | None = None,
    ) -> list[AdvertisementRecord]: ...

    def select_ads(self, ad_ids: list[str]) -> None: ...

    def read_pending_ads(self) -> list[AdvertisementRecord]: ...

    def save_after_approval(self) -> SaveResult: ...

    def read_save_result(self) -> SaveResult | None: ...


class AdUploadBrowserAdapter(Protocol):
    def check_login(self) -> LoginState: ...

    def open_ad_management(self) -> None: ...

    def search_company(self, company_name: str) -> list[CompanyRecord]: ...

    def select_company(self, company_id: str) -> None: ...

    def search_tag(self, company_id: str, tag_name: str) -> list[TagRecord]: ...

    def select_tag(self, tag_id: str) -> None: ...

    def create_tag_after_approval(self, company_id: str, tag_name: str) -> TagRecord: ...

    def open_ad_create_form(self) -> None: ...

    def select_ad_type(self, ad_type: AdvertisementType) -> None: ...

    def fill_ad_metadata(self, payload: dict[str, Any]) -> None: ...

    def upload_local_asset(self, local_path: str) -> None: ...

    def read_ad_preview(self) -> AdvertisementRecord: ...

    def save_ad_after_approval(self) -> SaveResult: ...

    def read_saved_ad_result(self) -> SaveResult | None: ...
