from pathlib import Path

import pytest

from backend.app.browser.playwright_admin import PlaywrightAdminAdapter
from backend.app.core.config import Settings


BUSINESS_METHODS = {
    "check_login",
    "open_device_management",
    "search_device",
    "open_device_ad_config",
    "read_existing_device_ads",
    "search_ads",
    "select_ads",
    "read_pending_ads",
    "save_after_approval",
    "read_save_result",
    "open_ad_management",
    "search_company",
    "select_company",
    "search_tag",
    "select_tag",
    "create_tag_after_approval",
    "open_ad_create_form",
    "select_ad_type",
    "fill_ad_metadata",
    "upload_local_asset",
    "read_ad_preview",
    "save_ad_after_approval",
    "read_saved_ad_result",
    "from_settings",
}


def test_playwright_adapter_exposes_only_whitelisted_business_methods():
    public_methods = {
        name
        for name in dir(PlaywrightAdminAdapter)
        if not name.startswith("_") and callable(getattr(PlaywrightAdminAdapter, name))
    }

    assert public_methods == BUSINESS_METHODS
    assert "click" not in public_methods
    assert "type" not in public_methods
    assert "evaluate" not in public_methods


def test_playwright_adapter_reads_profile_config_from_settings(tmp_path):
    settings = Settings(
        admin_backend_url="https://admin.example.test",
        browser_profile_path=str(tmp_path / "profile"),
        browser_profile_alias="staging-owner",
    )

    adapter = PlaywrightAdminAdapter.from_settings(settings)

    assert adapter.base_url == "https://admin.example.test"
    assert adapter.profile_path == str(tmp_path / "profile")
    assert adapter.profile_alias == "staging-owner"
    assert not hasattr(adapter, "password")
    assert not hasattr(adapter, "cookies")


def test_playwright_login_check_requires_configured_selectors():
    adapter = PlaywrightAdminAdapter(base_url="https://admin.example.test")

    with pytest.raises(NotImplementedError, match="login success selector"):
        adapter.check_login()


def test_real_backend_checklist_documents_required_inputs():
    checklist = Path("docs/integration/real-backend-checklist.md").read_text(encoding="utf-8")

    for required in [
        "backend URL",
        "test company",
        "test tags",
        "test device",
        "test image advertisement",
        "test video advertisement",
        "selectors",
        "staging",
        "production",
    ]:
        assert required in checklist
