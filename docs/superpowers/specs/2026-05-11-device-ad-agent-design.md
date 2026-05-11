# Device Advertisement Agent Design

## Summary

Build a local, controlled agent system for operating the company's management backend through a browser. The first milestone implements one workflow: bind existing advertisements from the backend's advertisement library to a specified device.

The system will use a local Web console, Python FastAPI backend, LangGraph workflow orchestration, Playwright for browser automation, and Supabase for persistent task state, approvals, audit records, and optional artifacts. The first implementation will support a mock backend adapter while preserving the same interface expected for the real management system.

The agent must not freely operate the backend. It can only call explicitly whitelisted tools. Before any final save, it must verify that the selected device and advertisements match the owner's command, report the pending action, and wait for owner approval.

## Goals

- Accept natural language commands from the owner.
- Parse commands into a target device number, advertisement names, and an intended action.
- Confirm the parsed command before browser operation begins.
- Use the browser's existing management-system login state.
- If not logged in, stop and ask the owner to log in manually.
- Search the device list by device number.
- Bind advertisements that already exist in advertisement management.
- Stop and report when a device or advertisement cannot be uniquely identified.
- Require owner approval before saving.
- Record key audit events for traceability.
- Structure the project so future business agents can be added without rewriting the first workflow.

## Non-Goals

- The first version will not create or upload new advertisements.
- The first version will not store or read backend usernames or passwords.
- The first version will not modify device information.
- The first version will not delete devices, delete advertisements, or change system configuration.
- The first version will not automatically hand off to another agent when an advertisement is missing.
- The first version will not rely on the LLM to perform arbitrary browser clicks.

## First Workflow

The first workflow is "bind existing advertisements to a specified device."

Example command:

```text
帮我给设备 10086 添加五一促销广告和新品视频
```

The system should parse this as:

- Target device number: `10086`
- Advertisement names: `五一促销广告`, `新品视频`
- Action: bind existing advertisements to the device

Before operating the backend, the agent must show the parsed result and state the allowed scope:

```text
我理解为：目标设备号是 10086；要绑定的广告是：五一促销广告、新品视频。
本次只会进入设备管理进行广告绑定，不会创建广告、删除广告或修改设备信息。
请确认是否开始。
```

## Architecture

The system has five main parts.

1. Local Web console
   - Accepts natural language commands.
   - Shows parsed command confirmation.
   - Shows workflow progress and paused states.
   - Shows the pre-save verification report.
   - Provides the final approval button before save.

2. FastAPI backend
   - Exposes task APIs for the console.
   - Runs LangGraph workflows.
   - Stores audit records.
   - Coordinates browser sessions.

3. LangGraph workflow layer
   - Owns state transitions.
   - Routes the command to the correct business workflow.
   - Enforces pauses for owner confirmation.
   - Handles failure branches such as missing login, multiple matches, and permission violations.

4. Browser adapter layer
   - Provides narrow business methods such as `search_device`, `search_ad`, and `save_after_approval`.
   - Hides raw Playwright access from the agent workflow.
   - Starts with a `MockAdminAdapter`.
   - Later adds a `PlaywrightAdminAdapter` for the real management backend.

5. Safety and audit layer
   - Defines each agent's allowed actions.
   - Blocks non-whitelisted operations.
   - Records key steps and decisions.
   - Requires approval before final save.

6. Supabase persistence layer
   - Stores tasks, approvals, audit events, agent permissions, browser session metadata, and optional artifacts.
   - Uses Supabase Postgres as the source of truth for app state.
   - Uses Supabase Auth for Web console users when the system moves beyond a single local operator.
   - Uses Supabase Realtime to stream task progress and approval changes to the Web console.
   - Uses Supabase Storage only for optional screenshots, traces, or exported reports.

## Supabase Database Design

The database stores the agent system's operational state. It does not mirror the company's management-system database and does not store management-system credentials.

Supabase products used:

- Postgres: primary relational database for tasks, approvals, permissions, and audit.
- Auth: console user identity and role mapping.
- Realtime: progress updates from task and audit tables to the local Web console.
- Storage: private bucket for optional screenshots or Playwright traces.

### Identity And Tenant Model

The first local version can run with one owner account, but the schema should support real company usage from the start.

Core tables:

- `organizations`
  - One company or operating unit.
  - Fields: `id`, `name`, `status`, `created_at`, `updated_at`.

- `profiles`
  - One row per Supabase Auth user.
  - Fields: `user_id`, `display_name`, `email`, `status`, `created_at`, `updated_at`.
  - `user_id` references `auth.users(id)`.

- `organization_members`
  - Maps users to organizations and roles.
  - Fields: `id`, `organization_id`, `user_id`, `role`, `status`, `created_at`.
  - Roles: `owner`, `operator`, `viewer`, `auditor`.

Role meaning:

- `owner`: can manage configuration, users, and permissions.
- `operator`: can create tasks and approve safe workflow gates.
- `viewer`: can view task progress and results.
- `auditor`: can view audit events but cannot approve or operate tasks.

### Agent And Permission Tables

Permissions must be data-driven and versioned so every task can be tied to the exact permission set it used.

- `agent_definitions`
  - Registered business agents.
  - Fields: `agent_key`, `name`, `description`, `status`, `created_at`.
  - Initial row: `device_ad_agent`.

- `agent_permission_sets`
  - Versioned whitelist and denylist for each agent.
  - Fields: `id`, `agent_key`, `version`, `allowed_actions`, `blocked_actions`, `status`, `created_by`, `created_at`, `deprecated_at`.
  - `allowed_actions` and `blocked_actions` are `jsonb` arrays.
  - Each task stores the permission set version it ran with.

Initial `device_ad_agent` allowed actions:

- `check_login`
- `open_management_backend`
- `open_device_management`
- `search_device`
- `open_device_ad_config`
- `search_existing_ad`
- `select_owner_approved_ad`
- `add_selected_ad_to_pending_list`
- `read_pending_ads`
- `save_after_owner_approval`
- `read_save_result`

### Backend Target And Browser Session Tables

These tables track metadata for real backend access without storing sensitive login material.

- `admin_targets`
  - Management-system environments.
  - Fields: `id`, `organization_id`, `name`, `environment`, `base_url`, `status`, `created_by`, `created_at`, `updated_at`.
  - Environments: `local_mock`, `staging`, `production`.
  - No username, password, cookie, or token fields.

- `browser_sessions`
  - Metadata for local Playwright persistent browser profiles.
  - Fields: `id`, `organization_id`, `owner_user_id`, `admin_target_id`, `profile_label`, `local_profile_ref`, `status`, `last_login_check_at`, `created_at`, `updated_at`.
  - `local_profile_ref` is a local identifier or path alias, not raw cookies.
  - Production cookies and management-system tokens must stay in the local browser profile, not in Supabase.

### Task Tables

- `agent_tasks`
  - Main task record.
  - Fields:
    - `id`
    - `organization_id`
    - `created_by`
    - `admin_target_id`
    - `browser_session_id`
    - `workflow_key`
    - `agent_key`
    - `permission_set_id`
    - `status`
    - `current_step`
    - `awaiting_action`
    - `original_command`
    - `parsed_command`
    - `target_device_no`
    - `requested_ads`
    - `matched_device`
    - `matched_ads`
    - `pending_save_report`
    - `error_code`
    - `error_message`
    - `created_at`
    - `updated_at`
    - `completed_at`

Task statuses:

- `draft`
- `awaiting_command_confirmation`
- `awaiting_login`
- `running`
- `awaiting_candidate_selection`
- `awaiting_save_approval`
- `saving`
- `succeeded`
- `failed`
- `cancelled`

`parsed_command`, `requested_ads`, `matched_device`, `matched_ads`, and `pending_save_report` should be `jsonb` so the workflow can store structured facts without premature schema churn. Stable, frequently queried fields such as `target_device_no`, `status`, `agent_key`, and `created_at` should remain first-class columns with indexes.

- `task_candidates`
  - Candidate objects shown to the owner when a device or advertisement search is ambiguous.
  - Fields: `id`, `task_id`, `candidate_type`, `external_ref`, `display_name`, `metadata`, `selection_status`, `created_at`, `selected_at`, `selected_by`.
  - Candidate types: `device`, `advertisement`.

- `task_approvals`
  - Human-in-the-loop approval records.
  - Fields:
    - `id`
    - `task_id`
    - `approval_type`
    - `status`
    - `requested_payload`
    - `decision_payload`
    - `requested_at`
    - `decided_at`
    - `decided_by`
    - `expires_at`
  - Approval types: `command_confirmation`, `login_complete`, `candidate_selection`, `save_approval`.
  - Approval statuses: `pending`, `approved`, `rejected`, `expired`.

The final save can only proceed when the task has an approved `save_approval` record whose payload matches the current `pending_save_report` hash.

### Workflow Persistence

LangGraph should use Postgres-backed checkpointing when the workflow needs reliable pause and resume. Supabase Postgres can host the checkpoint tables.

Application tables should still keep an app-facing task summary in `agent_tasks`. LangGraph checkpoint tables should be treated as internal workflow state, not as the product-facing audit trail.

Recommended split:

- LangGraph checkpointer stores graph state and resume data.
- `agent_tasks` stores the current business-visible status.
- `audit_events` stores append-only history.

### Audit Tables

- `audit_events`
  - Append-only history of important steps.
  - Fields:
    - `id`
    - `organization_id`
    - `task_id`
    - `actor_type`
    - `actor_user_id`
    - `agent_key`
    - `event_type`
    - `step_name`
    - `severity`
    - `summary`
    - `details`
    - `created_at`

Actor types:

- `owner`
- `operator`
- `agent`
- `system`

Audit records should not be edited by the client. Corrections should be new audit events, not updates to existing events.

### Artifact Storage

Screenshots and Playwright traces are useful in real incidents, but they can contain sensitive management-system data.

The first version should not capture screenshots by default. When artifacts are enabled:

- Store files in a private Supabase Storage bucket named `agent-artifacts`.
- Store metadata in `task_artifacts`.
- Apply short retention by default.
- Mask or avoid sensitive fields when possible.

- `task_artifacts`
  - Fields: `id`, `organization_id`, `task_id`, `artifact_type`, `storage_bucket`, `storage_path`, `mime_type`, `sha256`, `sensitivity`, `redaction_status`, `created_at`.
  - Artifact types: `screenshot`, `playwright_trace`, `report_export`.

### Concurrency And Locking

Real browser automation should avoid two tasks fighting over the same browser profile or same device workflow.

- `resource_locks`
  - Fields: `id`, `organization_id`, `lock_key`, `task_id`, `locked_by`, `locked_until`, `created_at`.
  - Example lock keys:
    - `browser_session:<browser_session_id>`
    - `device:<target_device_no>`

Locks should expire automatically if a worker dies. A save operation must re-check the pending state before clicking save, even if the task holds a lock.

### Indexes

Recommended initial indexes:

- `organization_members(user_id, organization_id)`
- `agent_tasks(organization_id, status, created_at desc)`
- `agent_tasks(organization_id, created_by, created_at desc)`
- `agent_tasks(target_device_no)`
- `task_approvals(task_id, status, approval_type)`
- `task_candidates(task_id, candidate_type)`
- `audit_events(organization_id, task_id, created_at desc)`
- `audit_events(organization_id, created_at desc)`
- `resource_locks(lock_key, locked_until)`

### Row Level Security

All application tables in exposed schemas must have Row Level Security enabled.

Policy direction:

- Authenticated organization members can read tasks in their organization.
- `owner` and `operator` can create tasks.
- `owner` and `operator` can decide approvals for tasks in their organization.
- `viewer` can read task summaries but cannot approve.
- `auditor` can read audit events but cannot create or modify tasks.
- Browser clients cannot directly insert privileged audit events or force task status transitions.
- Backend worker processes use the Supabase secret or service role key only on the server side after performing their own authorization checks.

The Web console must never receive the Supabase secret key or legacy service role key.

### Realtime Usage

The Web console subscribes to task-specific changes so the owner can see progress without polling.

Initial Realtime tables:

- `agent_tasks`
- `task_approvals`
- `task_candidates`
- `audit_events`

Realtime payloads should stay small. Large screenshots, full DOM dumps, Playwright traces, and raw page HTML should be stored as artifacts or local files, not streamed through Realtime.

### Data Retention

Default retention should be conservative and configurable:

- Task summaries: 365 days.
- Audit events: 365 days or company compliance requirement, whichever is longer.
- Failure screenshots and traces: 30 to 90 days.
- Successful task artifacts: disabled by default.

Retention jobs should delete artifacts before deleting their metadata and should never delete audit rows without an explicit retention policy.

## Agent Model

The first version includes these roles:

- Task Router Agent
  - Parses the user's command.
  - Determines the target business workflow.
  - Checks whether the requested action is in scope.

- Device Advertisement Agent
  - Handles only device advertisement binding.
  - Uses only device-advertisement tools.
  - Cannot upload advertisements, delete data, or modify device profile fields.

Future agents can be added later:

- Advertisement Upload Agent
  - Uploads image or video advertisements.
  - Fills advertisement metadata.
  - Requires its own permission whitelist and confirmation gates.

- Device Management Agent
  - Handles device status queries first.
  - Any modification workflow must be separately designed and guarded.

Cross-agent handoff must be explicit. For example, if an advertisement does not exist, the Device Advertisement Agent stops and reports the missing advertisement. It must not automatically start the Advertisement Upload Agent.

## Device Advertisement Workflow

The workflow proceeds through these states:

1. Receive natural language command.
2. Parse command into device number, advertisement names, and action.
3. Ask owner to confirm the parsed command.
4. Check backend login state.
5. If not logged in, ask owner to log in manually and pause.
6. Open device management.
7. Search for the device number.
8. Require exactly one matching device.
9. Open the device's advertisement configuration entry.
10. Search for each requested advertisement.
11. If an advertisement has multiple candidates, list candidates and ask the owner to choose.
12. If an advertisement is missing, stop and report.
13. Add selected advertisements to the pending save list.
14. Read the pending save list from the page.
15. Compare pending device and advertisements with the original confirmed command.
16. Show a pre-save report to the owner.
17. Save only after owner approval.
18. Read the save result and report success or failure.
19. Write final audit entries.

## Allowed Actions

The first version allows only these actions:

- Check login status.
- Open the management backend URL.
- Open device management.
- Search by device number.
- Open the advertisement configuration entry for the uniquely matched device.
- Search existing advertisements by advertisement name.
- Select owner-approved advertisement candidates.
- Add selected advertisements to the pending list.
- Read the pending list for verification.
- Save after owner approval.
- Read and report the save result.

## Blocked Actions

The first version must block these actions:

- Create advertisements.
- Upload advertisement images or videos.
- Delete advertisements.
- Delete devices.
- Modify device profile information.
- Change system configuration.
- Perform batch operations outside the confirmed device.
- Save before owner approval.
- Continue when the page structure, button meaning, or target object is uncertain.
- Use backend credentials stored in configuration.

## Matching Rules

Device matching:

- The device number should produce exactly one backend result.
- If no device is found, stop and report.
- If multiple devices are found, stop and ask for a more precise identifier.

Advertisement matching:

- If an advertisement name produces exactly one clear result, continue.
- If multiple candidates are found, list candidates and ask the owner to choose.
- If no advertisement is found, stop and report that this must be handled by a future Advertisement Upload Agent.
- Candidate reports should include available identifying fields, such as name, type, ID, status, and effective time, when the backend exposes them.

## Login Handling

The agent will not store or read backend usernames or passwords.

The browser should use a persistent browser profile so login cookies can survive across runs. On task start, the agent opens the management backend and checks whether it is already logged in.

If the browser is not logged in:

- The workflow pauses.
- The Web console asks the owner to log in manually.
- After the owner confirms login is complete, the workflow checks login state again.

## Approval Gate

Before final save, the agent must produce a pre-save verification report containing:

- Original owner command.
- Parsed device number.
- Matched device details.
- Requested advertisement names.
- Matched advertisement details.
- Pending page state read from the browser.
- A statement that the agent did not create advertisements, delete data, or modify device profile information.

The save button in the workflow is enabled only after the owner approves this report.

## Audit Logging

The first version records key step-level audit events:

- Task created.
- Command parsed.
- Owner confirmed parsed command.
- Login state checked.
- Device search completed.
- Advertisement search completed.
- Candidate selection requested or completed.
- Pre-save verification generated.
- Owner approved or rejected save.
- Save attempted.
- Final result reported.

Each audit event should include:

- Task ID.
- Timestamp.
- Agent name.
- Step name.
- Status.
- Structured details relevant to that step.

Screenshots are not required by default in the first version. The design should leave room to add screenshots later for failure cases, with sensitive information masking considered separately.

## Suggested Project Structure

```text
ztjy-agent/
  backend/
    app/
      main.py
      agents/
        router.py
        device_ad_agent.py
      workflows/
        device_ad_graph.py
      browser/
        adapters.py
        mock_admin.py
        playwright_admin.py
      safety/
        permissions.py
        approvals.py
      audit/
        models.py
        store.py
      db/
        supabase.py
        repositories.py
        rls_notes.md
    tests/
  frontend/
    src/
      pages/
      components/
      api/
  supabase/
    migrations/
    seed.sql
  docs/
    superpowers/
      specs/
```

## Implementation Strategy

The first build should use a mock adapter to validate the workflow, permissions, approval gates, and audit logging before connecting to the real backend.

The browser adapter interface should be designed to match real backend operations:

- `check_login()`
- `open_device_management()`
- `search_device(device_no)`
- `open_device_ad_config(device_id)`
- `search_ad(ad_name)`
- `select_ad(ad_id)`
- `read_pending_ads()`
- `save_after_approval()`
- `read_save_result()`

The mock adapter and real Playwright adapter should implement the same interface so the workflow does not need to change when real backend access is added.

Supabase should be integrated early, even while the backend adapter is mocked. The first implementation should create the task, approval, permission, and audit tables in Supabase migrations and use those tables for the Web console state instead of in-memory state. This keeps the first build aligned with real production behavior.

Environment configuration should separate public browser configuration from server-only secrets:

- Frontend: Supabase project URL and publishable or anon key.
- Backend: Supabase project URL plus server-only secret or service role key.
- Local only: browser profile path or alias.

Server-only Supabase keys must never be sent to the frontend or stored in client-side code.

## Testing Requirements

The first implementation should include tests for:

- Natural language command parsing.
- Permission whitelist enforcement.
- Device not found.
- Multiple devices found.
- Advertisement not found.
- Multiple advertisement candidates.
- Pre-save verification mismatch.
- Save blocked before owner approval.
- Successful happy path with mock adapter.
- Audit events written for key steps.
- Supabase task persistence across backend restart.
- RLS policies preventing cross-organization reads.
- RLS policies preventing viewers and auditors from approving tasks.
- Backend-only writes for privileged audit events.
- Realtime progress updates for task status and approval changes.

## Open Implementation Inputs

These details are intentionally deferred until real backend integration:

- Management backend URL.
- Test device numbers.
- Test advertisement names.
- Actual menu paths and page selectors.
- Whether the backend has a staging environment.
- Fields available in device and advertisement search results.
- Supabase project URL.
- Supabase frontend key.
- Supabase backend secret or service role key.
- Organization and operator account setup.
- Artifact retention policy.

These are not blockers for building the first workflow skeleton with a mock adapter.
