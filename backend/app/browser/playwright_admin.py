from __future__ import annotations

from typing import Any

from backend.app.browser.adapters import (
    AdvertisementRecord,
    CompanyRecord,
    LoginState,
    SaveResult,
    TagRecord,
)
from backend.app.core.config import Settings
from backend.app.workflows.state import AdvertisementType


class PlaywrightAdminAdapter:
    """Guarded skeleton for real management-backend automation."""

    def __init__(
        self,
        base_url: str,
        profile_path: str | None = None,
        profile_alias: str | None = None,
        login_success_selector: str | None = None,
    ) -> None:
        self.base_url = base_url
        self.profile_path = profile_path
        self.profile_alias = profile_alias
        self.login_success_selector = login_success_selector

    @classmethod
    def from_settings(cls, settings: Settings) -> "PlaywrightAdminAdapter":
        return cls(
            base_url=settings.admin_backend_url,
            profile_path=settings.browser_profile_path or None,
            profile_alias=settings.browser_profile_alias or None,
            login_success_selector=settings.playwright_login_success_selector or None,
        )

    def check_login(self) -> LoginState:
        if not self.login_success_selector:
            raise NotImplementedError("Playwright login success selector is not configured")
        raise NotImplementedError("Playwright login check requires a real browser page binding")

    def open_device_management(self) -> None:
        raise NotImplementedError("Playwright device-management navigation requires real backend selectors")

    def search_device(self, device_no: str) -> list[Any]:
        raise NotImplementedError("Playwright device search requires real backend selectors")

    def open_device_ad_config(self, device_id: str) -> None:
        raise NotImplementedError("Playwright device advertisement config requires real backend selectors")

    def read_existing_device_ads(self) -> list[AdvertisementRecord]:
        raise NotImplementedError("Playwright existing advertisement read requires real backend selectors")

    def search_ads(
        self,
        name: str,
        ad_type: AdvertisementType | None = None,
        category: str | None = None,
    ) -> list[AdvertisementRecord]:
        raise NotImplementedError("Playwright advertisement search requires real backend selectors")

    def select_ads(self, ad_ids: list[str]) -> None:
        raise NotImplementedError("Playwright advertisement selection requires real backend selectors")

    def read_pending_ads(self) -> list[AdvertisementRecord]:
        raise NotImplementedError("Playwright pending advertisement read requires real backend selectors")

    def save_after_approval(self) -> SaveResult:
        raise NotImplementedError("Playwright device advertisement save requires owner approval gate")

    def read_save_result(self) -> SaveResult | None:
        raise NotImplementedError("Playwright save result read requires real backend selectors")

    def open_ad_management(self) -> None:
        raise NotImplementedError("Playwright ad-management navigation requires real backend selectors")

    def search_company(self, company_name: str) -> list[CompanyRecord]:
        raise NotImplementedError("Playwright company search requires real backend selectors")

    def select_company(self, company_id: str) -> None:
        raise NotImplementedError("Playwright company selection requires real backend selectors")

    def search_tag(self, company_id: str, tag_name: str) -> list[TagRecord]:
        raise NotImplementedError("Playwright tag search requires real backend selectors")

    def select_tag(self, tag_id: str) -> None:
        raise NotImplementedError("Playwright tag selection requires real backend selectors")

    def create_tag_after_approval(self, company_id: str, tag_name: str) -> TagRecord:
        raise NotImplementedError("Playwright tag creation requires owner approval gate and selectors")

    def open_ad_create_form(self) -> None:
        raise NotImplementedError("Playwright ad creation form navigation requires real backend selectors")

    def select_ad_type(self, ad_type: AdvertisementType) -> None:
        raise NotImplementedError("Playwright ad type selection requires real backend selectors")

    def fill_ad_metadata(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError("Playwright metadata fill requires real backend selectors")

    def upload_local_asset(self, local_path: str) -> None:
        raise NotImplementedError("Playwright local asset upload requires real backend selectors")

    def read_ad_preview(self) -> AdvertisementRecord:
        raise NotImplementedError("Playwright ad preview read requires real backend selectors")

    def save_ad_after_approval(self) -> SaveResult:
        raise NotImplementedError("Playwright advertisement save requires owner approval gate")

    def read_saved_ad_result(self) -> SaveResult | None:
        raise NotImplementedError("Playwright saved advertisement read requires real backend selectors")
