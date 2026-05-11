import pytest

from backend.app.browser.adapters import BrowserOperationError
from backend.app.browser.mock_admin import MockAdminAdapter
from backend.app.browser.playwright_admin import PlaywrightAdminAdapter
from backend.app.workflows.state import AdvertisementType


def test_mock_admin_searches_device_and_reads_existing_ads():
    adapter = MockAdminAdapter.with_default_fixtures()

    devices = adapter.search_device("10086")
    adapter.open_device_ad_config(devices[0].id)

    existing_ads = adapter.read_existing_device_ads()

    assert devices[0].device_no == "10086"
    assert [ad.name for ad in existing_ads] == ["Existing lobby image"]


def test_mock_admin_searches_ads_by_type_and_category():
    adapter = MockAdminAdapter.with_default_fixtures()

    ads = adapter.search_ads(
        name="May",
        ad_type=AdvertisementType.VIDEO,
        category="holiday",
    )

    assert [ad.name for ad in ads] == ["May promo video"]


def test_mock_admin_select_ads_requires_known_exact_ids():
    adapter = MockAdminAdapter.with_default_fixtures()
    device = adapter.search_device("10086")[0]
    adapter.open_device_ad_config(device.id)
    ad = adapter.search_ads("May", ad_type=AdvertisementType.VIDEO)[0]

    with pytest.raises(BrowserOperationError, match="unknown advertisement"):
        adapter.select_ads([ad.id, "missing-ad"])

    adapter.select_ads([ad.id])
    pending_ads = adapter.read_pending_ads()

    assert [ad.name for ad in pending_ads] == ["Existing lobby image", "May promo video"]


def test_mock_admin_saves_selected_device_ads_after_approval():
    adapter = MockAdminAdapter.with_default_fixtures()
    device = adapter.search_device("10086")[0]
    adapter.open_device_ad_config(device.id)
    ad = adapter.search_ads("May", ad_type=AdvertisementType.VIDEO)[0]
    adapter.select_ads([ad.id])

    result = adapter.save_after_approval()

    assert result.succeeded is True
    assert result.saved_ids == [ad.id]
    assert adapter.read_save_result() == result
    assert [ad.name for ad in adapter.read_existing_device_ads()] == [
        "Existing lobby image",
        "May promo video",
    ]


def test_mock_admin_company_tag_creation_and_selection():
    adapter = MockAdminAdapter.with_default_fixtures()

    company = adapter.search_company("Company A")[0]
    adapter.select_company(company.id)
    assert adapter.search_tag(company.id, "Spring") == []

    tag = adapter.create_tag_after_approval(company.id, "Spring")
    adapter.select_tag(tag.id)

    assert tag.name == "Spring"
    assert adapter.search_tag(company.id, "Spring") == [tag]


def test_mock_admin_uploads_and_saves_one_ad_item():
    adapter = MockAdminAdapter.with_default_fixtures()
    company = adapter.search_company("Company A")[0]
    tag = adapter.create_tag_after_approval(company.id, "Spring")

    adapter.select_company(company.id)
    adapter.select_tag(tag.id)
    adapter.open_ad_create_form()
    adapter.select_ad_type(AdvertisementType.IMAGE)
    adapter.fill_ad_metadata({"name": "Spring poster", "category": "seasonal"})
    adapter.upload_local_asset("D:/ads/spring.jpg")

    preview = adapter.read_ad_preview()
    result = adapter.save_ad_after_approval()

    assert preview.name == "Spring poster"
    assert preview.ad_type == AdvertisementType.IMAGE
    assert result.succeeded is True
    assert adapter.read_saved_ad_result() == result
    assert adapter.search_ads("Spring poster", AdvertisementType.IMAGE) == [
        result.saved_ad,
    ]


def test_playwright_adapter_exposes_only_guarded_business_methods():
    public_methods = {
        name
        for name in dir(PlaywrightAdminAdapter)
        if not name.startswith("_") and callable(getattr(PlaywrightAdminAdapter, name))
    }

    assert "click" not in public_methods
    assert "type" not in public_methods
    assert "evaluate" not in public_methods
    assert "search_device" in public_methods
    assert "save_ad_after_approval" in public_methods
