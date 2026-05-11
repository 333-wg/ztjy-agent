from pathlib import Path


MIGRATION = Path("supabase/migrations/202605110001_core_schema.sql")
SEED = Path("supabase/seed.sql")


def _seed_block(sql: str, agent_key: str, next_marker: str) -> str:
    permission_sets = sql[sql.index("insert into public.agent_permission_sets") :]
    start = permission_sets.index(f"'{agent_key}',")
    end = permission_sets.index(next_marker, start)
    return permission_sets[start:end]


def test_migration_defines_core_tables():
    sql = MIGRATION.read_text(encoding="utf-8")
    for table in [
        "agent_tasks",
        "task_approvals",
        "audit_events",
        "agent_permission_sets",
        "task_candidates",
        "ad_upload_batches",
        "ad_upload_items",
        "local_asset_candidates",
        "resource_locks",
    ]:
        assert f"create table if not exists public.{table}" in sql.lower()


def test_migration_enables_rls():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "alter table public.agent_tasks enable row level security" in sql
    assert "alter table public.audit_events enable row level security" in sql


def test_migration_defines_recommended_indexes():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for index in [
        "idx_agent_tasks_organization_status_created_at",
        "idx_agent_tasks_organization_created_by_created_at",
        "idx_agent_tasks_target_device_no",
        "idx_task_approvals_task_status_type",
        "idx_task_approvals_task_subject",
        "idx_audit_events_organization_task_created_at",
        "idx_resource_locks_lock_key_locked_until",
    ]:
        assert index in sql


def test_migration_scopes_task_approvals_to_subjects():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    assert "subject_type text" in sql
    assert "subject_id uuid" in sql
    assert "on public.task_approvals (task_id, subject_type, subject_id)" in sql


def test_migration_keeps_workflow_updates_backend_only():
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for table in [
        "agent_tasks",
        "task_candidates",
        "local_asset_candidates",
        "task_approvals",
    ]:
        assert f"on public.{table} for update" not in sql
    assert "workflow writes are performed by backend service role" in sql


def test_seed_defines_initial_agent_permission_sets():
    sql = SEED.read_text(encoding="utf-8").lower()
    for agent_key in ["device_ad_agent", "ad_upload_agent"]:
        assert agent_key in sql
    assert "version" in sql
    assert "allowed_actions" in sql


def test_seed_defines_device_ad_agent_actions():
    sql = SEED.read_text(encoding="utf-8").lower()
    block = _seed_block(sql, "device_ad_agent", "'ad_upload_agent',")
    for action in [
        "check_login",
        "open_device_management",
        "search_device",
        "open_device_ad_config",
        "select_owner_approved_ads",
        "save_after_owner_approval",
        "read_save_result",
    ]:
        assert action in block
    assert "upload_local_asset" not in block


def test_seed_defines_ad_upload_agent_actions():
    sql = SEED.read_text(encoding="utf-8").lower()
    block = _seed_block(sql, "ad_upload_agent", "on conflict (agent_key, version)")
    for action in [
        "check_login",
        "open_ad_management",
        "search_company",
        "select_owner_approved_company",
        "search_local_assets",
        "upload_local_asset",
        "save_ad_after_owner_approval",
        "read_saved_ad_result",
    ]:
        assert action in block
    assert "open_device_ad_config" not in block
