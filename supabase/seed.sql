insert into public.agent_definitions (agent_key, name, description, status)
values
    (
        'device_ad_agent',
        'Device Advertisement Agent',
        'Binds owner-approved advertisements to target devices in the management backend.',
        'active'
    ),
    (
        'ad_upload_agent',
        'Advertisement Upload Agent',
        'Uploads owner-approved local advertisement assets to company and tag targets.',
        'active'
    )
on conflict (agent_key) do update set
    name = excluded.name,
    description = excluded.description,
    status = excluded.status;

insert into public.agent_permission_sets (
    agent_key,
    version,
    allowed_actions,
    blocked_actions,
    status
)
values
    (
        'device_ad_agent',
        1,
        '[
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
            "read_save_result"
        ]'::jsonb,
        '[]'::jsonb,
        'active'
    ),
    (
        'ad_upload_agent',
        1,
        '[
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
            "read_saved_ad_result"
        ]'::jsonb,
        '[]'::jsonb,
        'active'
    )
on conflict (agent_key, version) do update set
    allowed_actions = excluded.allowed_actions,
    blocked_actions = excluded.blocked_actions,
    status = excluded.status,
    deprecated_at = null;
