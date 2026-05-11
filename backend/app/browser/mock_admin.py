from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from backend.app.browser.adapters import (
    AdvertisementRecord,
    BrowserOperationError,
    CompanyRecord,
    DeviceRecord,
    LoginState,
    SaveResult,
    TagRecord,
)
from backend.app.workflows.state import AdvertisementType


class MockAdminAdapter:
    def __init__(
        self,
        devices: list[DeviceRecord] | None = None,
        advertisements: list[AdvertisementRecord] | None = None,
        device_ads: dict[str, list[str]] | None = None,
        companies: list[CompanyRecord] | None = None,
        tags: list[TagRecord] | None = None,
        logged_in: bool = True,
    ) -> None:
        self._logged_in = logged_in
        self._devices = {device.id: deepcopy(device) for device in devices or []}
        self._advertisements = {ad.id: deepcopy(ad) for ad in advertisements or []}
        self._device_ads = deepcopy(device_ads or {})
        self._companies = {company.id: deepcopy(company) for company in companies or []}
        self._tags = {tag.id: deepcopy(tag) for tag in tags or []}
        self._current_device_id: str | None = None
        self._pending_device_ad_ids: list[str] | None = None
        self._last_device_save_result: SaveResult | None = None
        self._selected_company_id: str | None = None
        self._selected_tag_id: str | None = None
        self._draft_ad_type: AdvertisementType | None = None
        self._draft_metadata: dict[str, Any] = {}
        self._draft_local_path: str | None = None
        self._last_upload_save_result: SaveResult | None = None

    @classmethod
    def with_default_fixtures(cls) -> MockAdminAdapter:
        device = DeviceRecord(id="device-10086", device_no="10086", display_name="Lobby player")
        existing_ad = AdvertisementRecord(
            id="ad-existing-image",
            name="Existing lobby image",
            ad_type=AdvertisementType.IMAGE,
            category="lobby",
        )
        may_video = AdvertisementRecord(
            id="ad-may-video",
            name="May promo video",
            ad_type=AdvertisementType.VIDEO,
            category="holiday",
        )
        may_image = AdvertisementRecord(
            id="ad-may-image",
            name="May promo image",
            ad_type=AdvertisementType.IMAGE,
            category="holiday",
        )
        company = CompanyRecord(id="company-a", name="Company A")
        tag = TagRecord(id="tag-existing", company_id=company.id, name="Existing")
        return cls(
            devices=[device],
            advertisements=[existing_ad, may_video, may_image],
            device_ads={device.id: [existing_ad.id]},
            companies=[company],
            tags=[tag],
        )

    def check_login(self) -> LoginState:
        return LoginState(logged_in=self._logged_in, reason=None if self._logged_in else "manual_login_required")

    def open_device_management(self) -> None:
        self._require_login()

    def search_device(self, device_no: str) -> list[DeviceRecord]:
        self._require_login()
        return [
            deepcopy(device)
            for device in self._devices.values()
            if device.device_no == device_no
        ]

    def open_device_ad_config(self, device_id: str) -> None:
        self._require_login()
        if device_id not in self._devices:
            raise BrowserOperationError(f"unknown device: {device_id}")
        self._current_device_id = device_id
        self._pending_device_ad_ids = list(self._device_ads.get(device_id, []))

    def read_existing_device_ads(self) -> list[AdvertisementRecord]:
        device_id = self._require_device_context()
        return [deepcopy(self._advertisements[ad_id]) for ad_id in self._device_ads.get(device_id, [])]

    def search_ads(
        self,
        name: str,
        ad_type: AdvertisementType | None = None,
        category: str | None = None,
    ) -> list[AdvertisementRecord]:
        self._require_login()
        needle = name.casefold()
        results = []
        for ad in self._advertisements.values():
            if needle and needle not in ad.name.casefold():
                continue
            if ad_type is not None and ad.ad_type != ad_type:
                continue
            if category is not None and ad.category != category:
                continue
            results.append(deepcopy(ad))
        return results

    def select_ads(self, ad_ids: list[str]) -> None:
        self._require_device_context()
        if self._pending_device_ad_ids is None:
            raise BrowserOperationError("device advertisement config is not open")
        unknown_ids = [ad_id for ad_id in ad_ids if ad_id not in self._advertisements]
        if unknown_ids:
            raise BrowserOperationError(f"unknown advertisement ids: {', '.join(unknown_ids)}")
        for ad_id in ad_ids:
            if ad_id not in self._pending_device_ad_ids:
                self._pending_device_ad_ids.append(ad_id)

    def read_pending_ads(self) -> list[AdvertisementRecord]:
        if self._pending_device_ad_ids is None:
            raise BrowserOperationError("device advertisement config is not open")
        return [deepcopy(self._advertisements[ad_id]) for ad_id in self._pending_device_ad_ids]

    def save_after_approval(self) -> SaveResult:
        device_id = self._require_device_context()
        if self._pending_device_ad_ids is None:
            raise BrowserOperationError("device advertisement config is not open")
        original_ids = self._device_ads.get(device_id, [])
        saved_ids = [ad_id for ad_id in self._pending_device_ad_ids if ad_id not in original_ids]
        self._device_ads[device_id] = list(self._pending_device_ad_ids)
        self._last_device_save_result = SaveResult(succeeded=True, saved_ids=saved_ids)
        return deepcopy(self._last_device_save_result)

    def read_save_result(self) -> SaveResult | None:
        return deepcopy(self._last_device_save_result)

    def open_ad_management(self) -> None:
        self._require_login()

    def search_company(self, company_name: str) -> list[CompanyRecord]:
        self._require_login()
        needle = company_name.casefold()
        return [
            deepcopy(company)
            for company in self._companies.values()
            if needle in company.name.casefold()
        ]

    def select_company(self, company_id: str) -> None:
        self._require_login()
        if company_id not in self._companies:
            raise BrowserOperationError(f"unknown company: {company_id}")
        self._selected_company_id = company_id

    def search_tag(self, company_id: str, tag_name: str) -> list[TagRecord]:
        self._require_login()
        if company_id not in self._companies:
            raise BrowserOperationError(f"unknown company: {company_id}")
        needle = tag_name.casefold()
        return [
            deepcopy(tag)
            for tag in self._tags.values()
            if tag.company_id == company_id and needle in tag.name.casefold()
        ]

    def select_tag(self, tag_id: str) -> None:
        self._require_login()
        if tag_id not in self._tags:
            raise BrowserOperationError(f"unknown tag: {tag_id}")
        tag = self._tags[tag_id]
        if self._selected_company_id is not None and tag.company_id != self._selected_company_id:
            raise BrowserOperationError("tag does not belong to selected company")
        self._selected_tag_id = tag_id

    def create_tag_after_approval(self, company_id: str, tag_name: str) -> TagRecord:
        self._require_login()
        if company_id not in self._companies:
            raise BrowserOperationError(f"unknown company: {company_id}")
        tag = TagRecord(id=f"tag-{uuid4()}", company_id=company_id, name=tag_name)
        self._tags[tag.id] = tag
        return deepcopy(tag)

    def open_ad_create_form(self) -> None:
        self._require_login()
        if self._selected_company_id is None:
            raise BrowserOperationError("company must be selected before opening advertisement form")
        if self._selected_tag_id is None:
            raise BrowserOperationError("tag must be selected before opening advertisement form")
        self._draft_ad_type = None
        self._draft_metadata = {}
        self._draft_local_path = None

    def select_ad_type(self, ad_type: AdvertisementType) -> None:
        if ad_type not in {AdvertisementType.IMAGE, AdvertisementType.VIDEO}:
            raise BrowserOperationError(f"unsupported advertisement type: {ad_type}")
        self._draft_ad_type = ad_type

    def fill_ad_metadata(self, payload: dict[str, Any]) -> None:
        self._draft_metadata = deepcopy(payload)

    def upload_local_asset(self, local_path: str) -> None:
        if not local_path:
            raise BrowserOperationError("local asset path is required")
        self._draft_local_path = local_path

    def read_ad_preview(self) -> AdvertisementRecord:
        return self._build_draft_ad(ad_id="preview")

    def save_ad_after_approval(self) -> SaveResult:
        ad = self._build_draft_ad(ad_id=f"ad-{uuid4()}")
        self._advertisements[ad.id] = ad
        self._last_upload_save_result = SaveResult(succeeded=True, saved_ids=[ad.id], saved_ad=ad)
        return deepcopy(self._last_upload_save_result)

    def read_saved_ad_result(self) -> SaveResult | None:
        return deepcopy(self._last_upload_save_result)

    def _require_login(self) -> None:
        if not self._logged_in:
            raise BrowserOperationError("management backend login is required")

    def _require_device_context(self) -> str:
        self._require_login()
        if self._current_device_id is None:
            raise BrowserOperationError("device advertisement config is not open")
        return self._current_device_id

    def _build_draft_ad(self, ad_id: str) -> AdvertisementRecord:
        if self._selected_company_id is None:
            raise BrowserOperationError("company must be selected before saving advertisement")
        if self._selected_tag_id is None:
            raise BrowserOperationError("tag must be selected before saving advertisement")
        if self._draft_ad_type is None:
            raise BrowserOperationError("advertisement type must be selected")
        if self._draft_local_path is None:
            raise BrowserOperationError("local asset must be uploaded")
        name = str(self._draft_metadata.get("name") or self._draft_local_path.rsplit("/", 1)[-1])
        category = self._draft_metadata.get("category")
        return AdvertisementRecord(
            id=ad_id,
            name=name,
            ad_type=self._draft_ad_type,
            category=str(category) if category is not None else None,
            local_path_ref=self._draft_local_path,
            metadata={
                "company_id": self._selected_company_id,
                "tag_id": self._selected_tag_id,
                "form": deepcopy(self._draft_metadata),
            },
        )
