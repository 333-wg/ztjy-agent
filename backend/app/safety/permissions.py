from __future__ import annotations

from dataclasses import dataclass


DEVICE_AD_AGENT_ACTIONS = frozenset(
    {
        "check_login",
        "open_management_backend",
        "open_device_management",
        "search_device",
        "open_device_ad_config",
        "search_existing_ads",
        "filter_ads_by_type",
        "filter_ads_by_category",
        "select_owner_approved_ads",
        "add_selected_ad_to_pending_list",
        "read_pending_ads",
        "save_after_owner_approval",
        "read_save_result",
    }
)

AD_UPLOAD_AGENT_ACTIONS = frozenset(
    {
        "check_login",
        "open_management_backend",
        "open_ad_management",
        "search_company",
        "select_owner_approved_company",
        "search_tag",
        "select_owner_approved_tag",
        "create_tag_after_owner_approval",
        "search_local_assets",
        "open_ad_create_form",
        "select_ad_type",
        "fill_ad_metadata",
        "upload_local_asset",
        "read_ad_preview",
        "save_ad_after_owner_approval",
        "read_saved_ad_result",
    }
)


class PermissionDenied(Exception):
    """Raised when an agent attempts an action outside its permission set."""


@dataclass(frozen=True)
class PermissionSet:
    agent_key: str
    version: int
    allowed_actions: frozenset[str]
    blocked_actions: frozenset[str] = frozenset()

    @classmethod
    def for_device_ad_agent(cls) -> PermissionSet:
        return cls(
            agent_key="device_ad_agent",
            version=1,
            allowed_actions=DEVICE_AD_AGENT_ACTIONS,
        )

    @classmethod
    def for_ad_upload_agent(cls) -> PermissionSet:
        return cls(
            agent_key="ad_upload_agent",
            version=1,
            allowed_actions=AD_UPLOAD_AGENT_ACTIONS,
        )

    def require(self, action: str) -> str:
        if action in self.blocked_actions:
            raise PermissionDenied(f"{self.agent_key} is blocked from action: {action}")
        if action not in self.allowed_actions:
            raise PermissionDenied(f"{self.agent_key} is not allowed to perform action: {action}")
        return action
