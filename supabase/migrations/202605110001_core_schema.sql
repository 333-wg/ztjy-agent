create extension if not exists pgcrypto;

create table if not exists public.organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    status text not null default 'active'
        check (status in ('active', 'disabled')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    display_name text,
    email text,
    status text not null default 'active'
        check (status in ('active', 'disabled')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.organization_members (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null check (role in ('owner', 'operator', 'viewer', 'auditor')),
    status text not null default 'active'
        check (status in ('active', 'disabled')),
    created_at timestamptz not null default now(),
    unique (organization_id, user_id)
);

create table if not exists public.agent_definitions (
    agent_key text primary key,
    name text not null,
    description text,
    status text not null default 'active'
        check (status in ('active', 'disabled')),
    created_at timestamptz not null default now()
);

create table if not exists public.agent_permission_sets (
    id uuid primary key default gen_random_uuid(),
    agent_key text not null references public.agent_definitions(agent_key),
    version integer not null check (version > 0),
    allowed_actions jsonb not null default '[]'::jsonb
        check (jsonb_typeof(allowed_actions) = 'array'),
    blocked_actions jsonb not null default '[]'::jsonb
        check (jsonb_typeof(blocked_actions) = 'array'),
    status text not null default 'active'
        check (status in ('active', 'deprecated')),
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    deprecated_at timestamptz,
    unique (agent_key, version)
);

create table if not exists public.admin_targets (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    name text not null,
    environment text not null check (environment in ('local_mock', 'staging', 'production')),
    base_url text not null,
    status text not null default 'active'
        check (status in ('active', 'disabled')),
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.browser_sessions (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    owner_user_id uuid references auth.users(id) on delete set null,
    admin_target_id uuid references public.admin_targets(id) on delete set null,
    profile_label text not null,
    local_profile_ref text not null,
    status text not null default 'active'
        check (status in ('active', 'login_required', 'disabled')),
    last_login_check_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.agent_tasks (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    created_by uuid references auth.users(id) on delete set null,
    admin_target_id uuid references public.admin_targets(id) on delete set null,
    browser_session_id uuid references public.browser_sessions(id) on delete set null,
    workflow_key text not null,
    agent_key text not null references public.agent_definitions(agent_key),
    permission_set_id uuid references public.agent_permission_sets(id) on delete restrict,
    status text not null default 'draft' check (
        status in (
            'draft',
            'awaiting_command_confirmation',
            'awaiting_login',
            'running',
            'awaiting_candidate_selection',
            'awaiting_save_approval',
            'awaiting_correction_decision',
            'awaiting_upload_plan_confirmation',
            'awaiting_company_selection',
            'awaiting_tag_selection',
            'awaiting_tag_creation_confirmation',
            'awaiting_asset_selection',
            'uploading_asset',
            'awaiting_item_save_approval',
            'saving',
            'succeeded',
            'failed',
            'cancelled'
        )
    ),
    current_step text,
    awaiting_action text,
    original_command text not null,
    parsed_command jsonb not null default '{}'::jsonb,
    target_device_no text,
    requested_ads jsonb not null default '[]'::jsonb,
    matched_device jsonb,
    baseline_ads jsonb not null default '[]'::jsonb,
    task_added_ads jsonb not null default '[]'::jsonb,
    matched_ads jsonb not null default '[]'::jsonb,
    pending_save_report jsonb,
    error_code text,
    error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.task_candidates (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    task_id uuid not null references public.agent_tasks(id) on delete cascade,
    candidate_type text not null check (candidate_type in ('device', 'advertisement', 'company', 'tag')),
    external_ref text,
    display_name text not null,
    ad_type text check (ad_type in ('image', 'video', 'unknown')),
    category text,
    metadata jsonb not null default '{}'::jsonb,
    selection_status text not null default 'pending'
        check (selection_status in ('pending', 'selected', 'rejected')),
    created_at timestamptz not null default now(),
    selected_at timestamptz,
    selected_by uuid references auth.users(id) on delete set null
);

create table if not exists public.ad_upload_batches (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    task_id uuid not null references public.agent_tasks(id) on delete cascade,
    created_by uuid references auth.users(id) on delete set null,
    company_request jsonb,
    matched_company jsonb,
    tag_request jsonb,
    matched_tag jsonb,
    created_tag jsonb,
    status text not null default 'draft' check (
        status in (
            'draft',
            'awaiting_upload_plan_confirmation',
            'resolving_company',
            'resolving_tag',
            'awaiting_tag_creation_confirmation',
            'running',
            'completed',
            'failed',
            'cancelled'
        )
    ),
    total_items integer not null default 0 check (total_items >= 0),
    completed_items integer not null default 0 check (completed_items >= 0),
    failed_items integer not null default 0 check (failed_items >= 0),
    skipped_items integer not null default 0 check (skipped_items >= 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz
);

create table if not exists public.ad_upload_items (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    batch_id uuid not null references public.ad_upload_batches(id) on delete cascade,
    task_id uuid not null references public.agent_tasks(id) on delete cascade,
    item_order integer not null check (item_order > 0),
    requested_name text,
    requested_type text check (requested_type in ('image', 'video', 'unknown')),
    requested_category text,
    local_asset_query text,
    selected_asset_path text,
    selected_asset_metadata jsonb,
    form_payload jsonb,
    preview_payload jsonb,
    saved_ad jsonb,
    status text not null default 'pending' check (
        status in (
            'pending',
            'asset_candidates_found',
            'awaiting_asset_selection',
            'ready_to_upload',
            'uploading',
            'awaiting_item_save_approval',
            'saved',
            'failed',
            'skipped',
            'cancelled'
        )
    ),
    error_code text,
    error_message text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    unique (batch_id, item_order)
);

create table if not exists public.local_asset_candidates (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    task_id uuid not null references public.agent_tasks(id) on delete cascade,
    upload_item_id uuid not null references public.ad_upload_items(id) on delete cascade,
    file_name text not null,
    local_path_ref text not null,
    media_type text check (media_type in ('image', 'video', 'unknown')),
    metadata jsonb not null default '{}'::jsonb,
    selection_status text not null default 'pending'
        check (selection_status in ('pending', 'selected', 'rejected')),
    created_at timestamptz not null default now(),
    selected_at timestamptz,
    selected_by uuid references auth.users(id) on delete set null
);

create table if not exists public.task_approvals (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    task_id uuid not null references public.agent_tasks(id) on delete cascade,
    approval_type text not null
        check (approval_type in ('command_confirmation', 'login_complete', 'candidate_selection', 'save_approval')),
    subject_type text not null
        check (subject_type in ('task', 'candidate', 'upload_batch', 'upload_item', 'local_asset')),
    subject_id uuid not null,
    status text not null default 'pending'
        check (status in ('pending', 'approved', 'rejected', 'expired')),
    requested_payload jsonb not null default '{}'::jsonb,
    decision_payload jsonb,
    requested_at timestamptz not null default now(),
    decided_at timestamptz,
    decided_by uuid references auth.users(id) on delete set null,
    expires_at timestamptz,
    check (subject_type <> 'task' or subject_id = task_id)
);

create table if not exists public.audit_events (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    task_id uuid references public.agent_tasks(id) on delete set null,
    actor_type text not null check (actor_type in ('owner', 'operator', 'agent', 'system')),
    actor_user_id uuid references auth.users(id) on delete set null,
    agent_key text references public.agent_definitions(agent_key),
    event_type text not null,
    step_name text,
    severity text not null default 'info'
        check (severity in ('debug', 'info', 'warning', 'error')),
    summary text not null,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists public.task_artifacts (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    task_id uuid references public.agent_tasks(id) on delete cascade,
    artifact_type text not null
        check (artifact_type in ('screenshot', 'playwright_trace', 'report_export')),
    storage_bucket text not null default 'agent-artifacts',
    storage_path text not null,
    mime_type text,
    sha256 text,
    sensitivity text not null default 'internal'
        check (sensitivity in ('internal', 'sensitive')),
    redaction_status text not null default 'not_required'
        check (redaction_status in ('not_required', 'pending', 'redacted')),
    created_at timestamptz not null default now()
);

create table if not exists public.resource_locks (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    lock_key text not null,
    task_id uuid references public.agent_tasks(id) on delete cascade,
    locked_by text not null,
    locked_until timestamptz not null,
    created_at timestamptz not null default now(),
    unique (organization_id, lock_key)
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create or replace function public.prevent_organization_id_change()
returns trigger
language plpgsql
as $$
begin
    if new.organization_id is distinct from old.organization_id then
        raise exception 'cannot change organization_id';
    end if;

    return new;
end;
$$;

create or replace function public.assert_workflow_organization_consistency()
returns trigger
language plpgsql
set search_path = public
as $$
declare
    task_organization_id uuid;
    target_organization_id uuid;
    session_organization_id uuid;
    batch_organization_id uuid;
    batch_task_id uuid;
    item_organization_id uuid;
    item_task_id uuid;
    subject_organization_id uuid;
    subject_task_id uuid;
begin
    if tg_table_name = 'browser_sessions' then
        if new.admin_target_id is not null then
            select target.organization_id
              into target_organization_id
              from public.admin_targets target
             where target.id = new.admin_target_id;

            if target_organization_id is distinct from new.organization_id then
                raise exception 'browser_sessions admin_target_id organization mismatch';
            end if;
        end if;

    elsif tg_table_name = 'agent_tasks' then
        if new.admin_target_id is not null then
            select target.organization_id
              into target_organization_id
              from public.admin_targets target
             where target.id = new.admin_target_id;

            if target_organization_id is distinct from new.organization_id then
                raise exception 'agent_tasks admin_target_id organization mismatch';
            end if;
        end if;

        if new.browser_session_id is not null then
            select browser_session.organization_id
              into session_organization_id
              from public.browser_sessions browser_session
             where browser_session.id = new.browser_session_id;

            if session_organization_id is distinct from new.organization_id then
                raise exception 'agent_tasks browser_session_id organization mismatch';
            end if;
        end if;

    elsif tg_table_name = 'task_candidates' then
        select task.organization_id
          into task_organization_id
          from public.agent_tasks task
         where task.id = new.task_id;

        if task_organization_id is distinct from new.organization_id then
            raise exception 'task_candidates task_id organization mismatch';
        end if;

    elsif tg_table_name = 'task_approvals' then
        select task.organization_id
          into task_organization_id
          from public.agent_tasks task
         where task.id = new.task_id;

        if task_organization_id is distinct from new.organization_id then
            raise exception 'task_approvals task_id organization mismatch';
        end if;

        if new.subject_type = 'task' then
            if new.subject_id is distinct from new.task_id then
                raise exception 'task_approvals task subject mismatch';
            end if;

        elsif new.subject_type = 'candidate' then
            select candidate.organization_id, candidate.task_id
              into subject_organization_id, subject_task_id
              from public.task_candidates candidate
             where candidate.id = new.subject_id;

            if subject_organization_id is distinct from new.organization_id
                or subject_task_id is distinct from new.task_id then
                raise exception 'task_approvals candidate subject mismatch';
            end if;

        elsif new.subject_type = 'upload_batch' then
            select batch.organization_id, batch.task_id
              into subject_organization_id, subject_task_id
              from public.ad_upload_batches batch
             where batch.id = new.subject_id;

            if subject_organization_id is distinct from new.organization_id
                or subject_task_id is distinct from new.task_id then
                raise exception 'task_approvals upload_batch subject mismatch';
            end if;

        elsif new.subject_type = 'upload_item' then
            select item.organization_id, item.task_id
              into subject_organization_id, subject_task_id
              from public.ad_upload_items item
             where item.id = new.subject_id;

            if subject_organization_id is distinct from new.organization_id
                or subject_task_id is distinct from new.task_id then
                raise exception 'task_approvals upload_item subject mismatch';
            end if;

        elsif new.subject_type = 'local_asset' then
            select asset.organization_id, asset.task_id
              into subject_organization_id, subject_task_id
              from public.local_asset_candidates asset
             where asset.id = new.subject_id;

            if subject_organization_id is distinct from new.organization_id
                or subject_task_id is distinct from new.task_id then
                raise exception 'task_approvals local_asset subject mismatch';
            end if;
        end if;

    elsif tg_table_name = 'ad_upload_batches' then
        select task.organization_id
          into task_organization_id
          from public.agent_tasks task
         where task.id = new.task_id;

        if task_organization_id is distinct from new.organization_id then
            raise exception 'ad_upload_batches task_id organization mismatch';
        end if;

    elsif tg_table_name = 'ad_upload_items' then
        select task.organization_id
          into task_organization_id
          from public.agent_tasks task
         where task.id = new.task_id;

        if task_organization_id is distinct from new.organization_id then
            raise exception 'ad_upload_items task_id organization mismatch';
        end if;

        select batch.organization_id, batch.task_id
          into batch_organization_id, batch_task_id
          from public.ad_upload_batches batch
         where batch.id = new.batch_id;

        if batch_organization_id is distinct from new.organization_id then
            raise exception 'ad_upload_items batch_id organization mismatch';
        end if;

        if batch_task_id is distinct from new.task_id then
            raise exception 'ad_upload_items batch_id task mismatch';
        end if;

    elsif tg_table_name = 'local_asset_candidates' then
        select task.organization_id
          into task_organization_id
          from public.agent_tasks task
         where task.id = new.task_id;

        if task_organization_id is distinct from new.organization_id then
            raise exception 'local_asset_candidates task_id organization mismatch';
        end if;

        select item.organization_id, item.task_id
          into item_organization_id, item_task_id
          from public.ad_upload_items item
         where item.id = new.upload_item_id;

        if item_organization_id is distinct from new.organization_id then
            raise exception 'local_asset_candidates upload_item_id organization mismatch';
        end if;

        if item_task_id is distinct from new.task_id then
            raise exception 'local_asset_candidates upload_item_id task mismatch';
        end if;

    elsif tg_table_name = 'audit_events' then
        if new.task_id is not null then
            select task.organization_id
              into task_organization_id
              from public.agent_tasks task
             where task.id = new.task_id;

            if task_organization_id is distinct from new.organization_id then
                raise exception 'audit_events task_id organization mismatch';
            end if;
        end if;

    elsif tg_table_name = 'task_artifacts' then
        if new.task_id is not null then
            select task.organization_id
              into task_organization_id
              from public.agent_tasks task
             where task.id = new.task_id;

            if task_organization_id is distinct from new.organization_id then
                raise exception 'task_artifacts task_id organization mismatch';
            end if;
        end if;

    elsif tg_table_name = 'resource_locks' then
        if new.task_id is not null then
            select task.organization_id
              into task_organization_id
              from public.agent_tasks task
             where task.id = new.task_id;

            if task_organization_id is distinct from new.organization_id then
                raise exception 'resource_locks task_id organization mismatch';
            end if;
        end if;
    end if;

    return new;
end;
$$;

drop trigger if exists set_organizations_updated_at on public.organizations;
create trigger set_organizations_updated_at
before update on public.organizations
for each row execute function public.set_updated_at();

drop trigger if exists set_profiles_updated_at on public.profiles;
create trigger set_profiles_updated_at
before update on public.profiles
for each row execute function public.set_updated_at();

drop trigger if exists set_admin_targets_updated_at on public.admin_targets;
create trigger set_admin_targets_updated_at
before update on public.admin_targets
for each row execute function public.set_updated_at();

drop trigger if exists set_browser_sessions_updated_at on public.browser_sessions;
create trigger set_browser_sessions_updated_at
before update on public.browser_sessions
for each row execute function public.set_updated_at();

drop trigger if exists prevent_admin_targets_organization_move on public.admin_targets;
create trigger prevent_admin_targets_organization_move
before update of organization_id on public.admin_targets
for each row execute function public.prevent_organization_id_change();

drop trigger if exists prevent_browser_sessions_organization_move on public.browser_sessions;
create trigger prevent_browser_sessions_organization_move
before update of organization_id on public.browser_sessions
for each row execute function public.prevent_organization_id_change();

drop trigger if exists set_agent_tasks_updated_at on public.agent_tasks;
create trigger set_agent_tasks_updated_at
before update on public.agent_tasks
for each row execute function public.set_updated_at();

drop trigger if exists set_ad_upload_batches_updated_at on public.ad_upload_batches;
create trigger set_ad_upload_batches_updated_at
before update on public.ad_upload_batches
for each row execute function public.set_updated_at();

drop trigger if exists set_ad_upload_items_updated_at on public.ad_upload_items;
create trigger set_ad_upload_items_updated_at
before update on public.ad_upload_items
for each row execute function public.set_updated_at();

drop trigger if exists assert_browser_sessions_organization on public.browser_sessions;
create trigger assert_browser_sessions_organization
before insert or update of organization_id, admin_target_id on public.browser_sessions
for each row execute function public.assert_workflow_organization_consistency();

drop trigger if exists assert_agent_tasks_organization on public.agent_tasks;
create trigger assert_agent_tasks_organization
before insert or update of organization_id, admin_target_id, browser_session_id on public.agent_tasks
for each row execute function public.assert_workflow_organization_consistency();

drop trigger if exists assert_task_candidates_organization on public.task_candidates;
create trigger assert_task_candidates_organization
before insert or update of organization_id, task_id on public.task_candidates
for each row execute function public.assert_workflow_organization_consistency();

drop trigger if exists assert_task_approvals_organization on public.task_approvals;
create trigger assert_task_approvals_organization
before insert or update of organization_id, task_id, subject_type, subject_id on public.task_approvals
for each row execute function public.assert_workflow_organization_consistency();

drop trigger if exists assert_ad_upload_batches_organization on public.ad_upload_batches;
create trigger assert_ad_upload_batches_organization
before insert or update of organization_id, task_id on public.ad_upload_batches
for each row execute function public.assert_workflow_organization_consistency();

drop trigger if exists assert_ad_upload_items_organization on public.ad_upload_items;
create trigger assert_ad_upload_items_organization
before insert or update of organization_id, batch_id, task_id on public.ad_upload_items
for each row execute function public.assert_workflow_organization_consistency();

drop trigger if exists assert_local_asset_candidates_organization on public.local_asset_candidates;
create trigger assert_local_asset_candidates_organization
before insert or update of organization_id, task_id, upload_item_id on public.local_asset_candidates
for each row execute function public.assert_workflow_organization_consistency();

drop trigger if exists assert_audit_events_organization on public.audit_events;
create trigger assert_audit_events_organization
before insert or update of organization_id, task_id on public.audit_events
for each row execute function public.assert_workflow_organization_consistency();

drop trigger if exists assert_task_artifacts_organization on public.task_artifacts;
create trigger assert_task_artifacts_organization
before insert or update of organization_id, task_id on public.task_artifacts
for each row execute function public.assert_workflow_organization_consistency();

drop trigger if exists assert_resource_locks_organization on public.resource_locks;
create trigger assert_resource_locks_organization
before insert or update of organization_id, task_id on public.resource_locks
for each row execute function public.assert_workflow_organization_consistency();

create index if not exists idx_organization_members_user_organization
    on public.organization_members (user_id, organization_id);
create index if not exists idx_agent_tasks_organization_status_created_at
    on public.agent_tasks (organization_id, status, created_at desc);
create index if not exists idx_agent_tasks_organization_created_by_created_at
    on public.agent_tasks (organization_id, created_by, created_at desc);
create index if not exists idx_agent_tasks_target_device_no
    on public.agent_tasks (target_device_no);
create index if not exists idx_task_approvals_task_status_type
    on public.task_approvals (task_id, status, approval_type);
create index if not exists idx_task_approvals_task_subject
    on public.task_approvals (task_id, subject_type, subject_id);
create index if not exists idx_task_candidates_task_candidate_type
    on public.task_candidates (task_id, candidate_type);
create index if not exists idx_task_candidates_task_candidate_type_ad_type
    on public.task_candidates (task_id, candidate_type, ad_type);
create index if not exists idx_task_candidates_task_candidate_type_category
    on public.task_candidates (task_id, candidate_type, category);
create index if not exists idx_ad_upload_batches_organization_status_created_at
    on public.ad_upload_batches (organization_id, status, created_at desc);
create index if not exists idx_ad_upload_batches_task_id
    on public.ad_upload_batches (task_id);
create index if not exists idx_ad_upload_items_batch_item_order
    on public.ad_upload_items (batch_id, item_order);
create index if not exists idx_ad_upload_items_batch_status
    on public.ad_upload_items (batch_id, status);
create index if not exists idx_local_asset_candidates_upload_item_selection_status
    on public.local_asset_candidates (upload_item_id, selection_status);
create index if not exists idx_audit_events_organization_task_created_at
    on public.audit_events (organization_id, task_id, created_at desc);
create index if not exists idx_audit_events_organization_created_at
    on public.audit_events (organization_id, created_at desc);
create index if not exists idx_resource_locks_lock_key_locked_until
    on public.resource_locks (lock_key, locked_until);

create or replace function public.is_organization_member(check_organization_id uuid)
returns boolean
language sql
security definer
set search_path = public
stable
as $$
    select exists (
        select 1
        from public.organization_members member
        where member.organization_id = check_organization_id
          and member.user_id = auth.uid()
          and member.status = 'active'
    );
$$;

create or replace function public.has_organization_role(check_organization_id uuid, allowed_roles text[])
returns boolean
language sql
security definer
set search_path = public
stable
as $$
    select exists (
        select 1
        from public.organization_members member
        where member.organization_id = check_organization_id
          and member.user_id = auth.uid()
          and member.status = 'active'
          and member.role = any (allowed_roles)
    );
$$;

alter table public.organizations enable row level security;
alter table public.profiles enable row level security;
alter table public.organization_members enable row level security;
alter table public.agent_definitions enable row level security;
alter table public.agent_permission_sets enable row level security;
alter table public.admin_targets enable row level security;
alter table public.browser_sessions enable row level security;
alter table public.agent_tasks enable row level security;
alter table public.task_candidates enable row level security;
alter table public.ad_upload_batches enable row level security;
alter table public.ad_upload_items enable row level security;
alter table public.local_asset_candidates enable row level security;
alter table public.task_approvals enable row level security;
alter table public.audit_events enable row level security;
alter table public.task_artifacts enable row level security;
alter table public.resource_locks enable row level security;

comment on table public.admin_targets is
    'Organization ownership is immutable for tenancy safety. Moving an admin target across organizations could invalidate browser session and task relationship checks.';
comment on table public.browser_sessions is
    'Organization ownership is immutable for tenancy safety. Moving a browser session across organizations could invalidate task relationship checks.';
comment on table public.agent_tasks is
    'Workflow writes are performed by backend service role after app-level authorization. Tasks are created by backend service role after app-level authorization. Browser clients may read organization-scoped rows but cannot directly create or mutate workflow state.';
comment on table public.task_candidates is
    'Workflow writes are performed by backend service role after app-level authorization. Browser clients read candidates but do not directly change selection state.';
comment on table public.local_asset_candidates is
    'Workflow writes are performed by backend service role after app-level authorization. Browser clients read local asset candidates but do not directly change selection state.';
comment on table public.task_approvals is
    'Workflow writes are performed by backend service role after app-level authorization. Approval decisions are handled through backend APIs so browser clients cannot mutate requested approval fields.';

drop policy if exists "members can read organizations" on public.organizations;
create policy "members can read organizations"
on public.organizations for select
to authenticated
using (public.is_organization_member(id));

drop policy if exists "users can read own profile" on public.profiles;
create policy "users can read own profile"
on public.profiles for select
to authenticated
using (user_id = auth.uid());

drop policy if exists "users can update own profile" on public.profiles;
create policy "users can update own profile"
on public.profiles for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists "members can read organization members" on public.organization_members;
create policy "members can read organization members"
on public.organization_members for select
to authenticated
using (public.is_organization_member(organization_id));

drop policy if exists "authenticated can read active agent definitions" on public.agent_definitions;
create policy "authenticated can read active agent definitions"
on public.agent_definitions for select
to authenticated
using (status = 'active');

drop policy if exists "authenticated can read active permission sets" on public.agent_permission_sets;
create policy "authenticated can read active permission sets"
on public.agent_permission_sets for select
to authenticated
using (status = 'active');

drop policy if exists "members can read admin targets" on public.admin_targets;
create policy "members can read admin targets"
on public.admin_targets for select
to authenticated
using (public.is_organization_member(organization_id));

drop policy if exists "owners can manage admin targets" on public.admin_targets;
create policy "owners can manage admin targets"
on public.admin_targets for all
to authenticated
using (public.has_organization_role(organization_id, array['owner']))
with check (public.has_organization_role(organization_id, array['owner']));

drop policy if exists "members can read browser sessions" on public.browser_sessions;
create policy "members can read browser sessions"
on public.browser_sessions for select
to authenticated
using (public.is_organization_member(organization_id));

drop policy if exists "owners can manage browser sessions" on public.browser_sessions;
create policy "owners can manage browser sessions"
on public.browser_sessions for all
to authenticated
using (public.has_organization_role(organization_id, array['owner']))
with check (public.has_organization_role(organization_id, array['owner']));

drop policy if exists "members can read agent tasks" on public.agent_tasks;
create policy "members can read agent tasks"
on public.agent_tasks for select
to authenticated
using (public.is_organization_member(organization_id));

drop policy if exists "operators can create agent tasks" on public.agent_tasks;

drop policy if exists "operators can update agent tasks" on public.agent_tasks;

drop policy if exists "members can read task candidates" on public.task_candidates;
create policy "members can read task candidates"
on public.task_candidates for select
to authenticated
using (
    exists (
        select 1
        from public.agent_tasks task
        where task.id = task_id
          and public.is_organization_member(task.organization_id)
    )
);

drop policy if exists "operators can update task candidates" on public.task_candidates;

drop policy if exists "members can read upload batches" on public.ad_upload_batches;
create policy "members can read upload batches"
on public.ad_upload_batches for select
to authenticated
using (public.is_organization_member(organization_id));

drop policy if exists "members can read upload items" on public.ad_upload_items;
create policy "members can read upload items"
on public.ad_upload_items for select
to authenticated
using (public.is_organization_member(organization_id));

drop policy if exists "members can read local asset candidates" on public.local_asset_candidates;
create policy "members can read local asset candidates"
on public.local_asset_candidates for select
to authenticated
using (public.is_organization_member(organization_id));

drop policy if exists "operators can update local asset candidates" on public.local_asset_candidates;

drop policy if exists "members can read task approvals" on public.task_approvals;
create policy "members can read task approvals"
on public.task_approvals for select
to authenticated
using (
    exists (
        select 1
        from public.agent_tasks task
        where task.id = task_id
          and public.is_organization_member(task.organization_id)
    )
);

drop policy if exists "operators can decide task approvals" on public.task_approvals;
drop policy if exists "service role can manage task approvals" on public.task_approvals;
create policy "service role can manage task approvals"
on public.task_approvals for all
to service_role
using (true)
with check (true);

drop policy if exists "members can read audit events" on public.audit_events;
create policy "members can read audit events"
on public.audit_events for select
to authenticated
using (public.is_organization_member(organization_id));

drop policy if exists "service role can insert audit events" on public.audit_events;
create policy "service role can insert audit events"
on public.audit_events for insert
to service_role
with check (true);

drop policy if exists "members can read task artifacts" on public.task_artifacts;
create policy "members can read task artifacts"
on public.task_artifacts for select
to authenticated
using (public.is_organization_member(organization_id));

drop policy if exists "members can read resource locks" on public.resource_locks;
create policy "members can read resource locks"
on public.resource_locks for select
to authenticated
using (public.is_organization_member(organization_id));
