from pathlib import Path


MIGRATION = Path("supabase/migrations/202605110001_core_schema.sql")
SEED = Path("supabase/seed.sql")


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
        "idx_audit_events_organization_task_created_at",
        "idx_resource_locks_lock_key_locked_until",
    ]:
        assert index in sql


def test_seed_defines_initial_agent_permission_sets():
    sql = SEED.read_text(encoding="utf-8").lower()
    for agent_key in ["device_ad_agent", "ad_upload_agent"]:
        assert agent_key in sql
    assert "version" in sql
    assert "allowed_actions" in sql
