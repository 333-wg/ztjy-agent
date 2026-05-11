# Supabase Setup Runbook

## Environment Variables

Copy `.env.example` to `.env` and fill:

```text
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
LANGGRAPH_CHECKPOINTER=postgres
LANGGRAPH_POSTGRES_URL=
LANGGRAPH_POSTGRES_SETUP=false
```

The service role key is server-only. It must not be sent to frontend DTOs or stored in browser-accessible configuration.

`LANGGRAPH_POSTGRES_URL` is the Supabase Postgres connection string, not the Supabase REST URL.
Set `LANGGRAPH_POSTGRES_SETUP=true` only during an intentional checkpoint table setup run, then switch it back to `false`.

## Schema

Migration:

```text
supabase/migrations/202605110001_core_schema.sql
```

Seed:

```text
supabase/seed.sql
```

The schema includes organizations, users, agent definitions, permission sets, tasks, approvals, candidates, upload batches/items, local asset candidates, audit events, artifacts, browser sessions, admin targets, and resource locks.

LangGraph checkpoint tables are internal workflow state. The app-facing task status, approvals, candidates, upload queue, and audit trail still live in the application tables above.

Thread IDs are stable and scoped:

- Device binding graph: `device_ad_binding:{task_id}`
- Upload item graph: `ad_upload_item:{task_id}:{item_id}`

## Validation

Contract tests:

```powershell
uv run pytest tests/test_supabase_migration_contract.py -v
```

If Supabase CLI is configured for the project:

```powershell
supabase db reset
```

## Policy Notes

- Workflow writes are backend-service-only.
- Task approval subjects are validated against their parent task and organization.
- Tenant moves for parent records are blocked by trigger protections.
- RLS allows organization-scoped reads and controlled backend writes.
