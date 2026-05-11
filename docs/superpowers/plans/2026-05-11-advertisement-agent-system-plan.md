# Advertisement Agent System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, testable agent system that routes natural-language commands to controlled workflows for device advertisement binding and advertisement upload.

**Architecture:** FastAPI exposes task APIs used by a local Web console. LangGraph owns workflow state and human approval pauses. Browser operations go through narrow adapter interfaces, with mock adapters first and Playwright adapters later. Supabase stores tasks, approvals, audit events, permissions, and upload queue state.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, LangGraph, Playwright Python, Supabase Postgres migrations, pytest, React + Vite + TypeScript.

---

## Scope Notes

This plan is staged because the spec contains two related workflows.

- Phase 1 creates the foundation and the Device Advertisement Agent MVP with a mock backend adapter.
- Phase 2 adds the Advertisement Upload Agent with sequential upload items, local asset search, tag creation approval, and mock upload behavior.
- Real Playwright selectors for the company management backend are intentionally scaffolded but not fully implemented until the real page paths and test data are available.

The first working milestone should pass tests without a real management backend and without uploading real files.

## File Structure

- `pyproject.toml`: backend dependencies, pytest config entry points.
- `.env.example`: required environment variables without secrets.
- `backend/app/main.py`: FastAPI app factory and router registration.
- `backend/app/core/config.py`: environment-driven settings.
- `backend/app/api/schemas.py`: request and response DTOs.
- `backend/app/api/routes.py`: task, approval, and status endpoints.
- `backend/app/agents/router.py`: deterministic intent router plus LLM-ready abstraction.
- `backend/app/agents/device_ad_agent.py`: device binding workflow service wrapper.
- `backend/app/agents/ad_upload_agent.py`: advertisement upload workflow service wrapper.
- `backend/app/workflows/state.py`: shared task state models.
- `backend/app/workflows/device_ad_graph.py`: LangGraph for device advertisement binding.
- `backend/app/workflows/ad_upload_graph.py`: LangGraph for sequential advertisement upload items.
- `backend/app/browser/adapters.py`: browser adapter protocols and data classes.
- `backend/app/browser/mock_admin.py`: in-memory mock management backend.
- `backend/app/browser/playwright_admin.py`: Playwright adapter skeleton with guarded methods.
- `backend/app/assets/local_search.py`: local asset search by filename/keyword.
- `backend/app/assets/media_validation.py`: media type and extension validation.
- `backend/app/safety/permissions.py`: agent action whitelist enforcement.
- `backend/app/safety/approvals.py`: approval matching and hash checks.
- `backend/app/audit/models.py`: audit event types and payload models.
- `backend/app/audit/store.py`: audit write/read abstraction.
- `backend/app/db/supabase.py`: Supabase client creation and server-only key handling.
- `backend/app/db/repositories.py`: repository interfaces plus Supabase and in-memory implementations.
- `supabase/migrations/202605110001_core_schema.sql`: core tables, indexes, and RLS policies.
- `supabase/seed.sql`: initial agents and permission sets.
- `frontend/package.json`: Web console dependencies and scripts.
- `frontend/src/App.tsx`: local console shell.
- `frontend/src/api/client.ts`: backend API client.
- `frontend/src/components/*`: command form, task timeline, approvals, candidates, upload items.
- `tests/`: backend tests mirroring each workflow and safety rule.

---

### Task 1: Backend Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes.py`
- Create: `backend/app/api/schemas.py`
- Test: `tests/test_app_health.py`

- [ ] **Step 1: Write the failing health test**

```python
from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_check_returns_ok():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_app_health.py -v`

Expected: FAIL because `backend.app.main` does not exist.

- [ ] **Step 3: Create the minimal FastAPI app**

Create `backend/app/main.py` with `create_app()` and `/health`.

- [ ] **Step 4: Add project dependencies**

Use `pyproject.toml` with FastAPI, uvicorn, pydantic-settings, pytest, httpx, langgraph, playwright, and supabase.

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/test_app_health.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example backend tests/test_app_health.py
git commit -m "chore: scaffold backend app"
```

---

### Task 2: Supabase Schema And Seed Files

**Files:**
- Create: `supabase/migrations/202605110001_core_schema.sql`
- Create: `supabase/seed.sql`
- Create: `tests/test_supabase_migration_contract.py`

- [ ] **Step 1: Write migration contract tests**

Test that the migration contains required tables, RLS enables, indexes, and seedable agent keys.

```python
from pathlib import Path


MIGRATION = Path("supabase/migrations/202605110001_core_schema.sql")


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_supabase_migration_contract.py -v`

Expected: FAIL because the migration does not exist.

- [ ] **Step 3: Add SQL migration**

Define tables from the spec:

- identity: `organizations`, `profiles`, `organization_members`
- permissions: `agent_definitions`, `agent_permission_sets`
- targets: `admin_targets`, `browser_sessions`
- tasks: `agent_tasks`, `task_candidates`, `task_approvals`
- uploads: `ad_upload_batches`, `ad_upload_items`, `local_asset_candidates`
- audit and artifacts: `audit_events`, `task_artifacts`
- locking: `resource_locks`

Enable RLS on application tables and add initial organization-scoped policies. Policies can start conservative: authenticated members read rows in their organization, backend service role writes privileged events.

- [ ] **Step 4: Add seed data**

Seed `device_ad_agent`, `ad_upload_agent`, and version `1` permission sets.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_supabase_migration_contract.py -v`

Expected: PASS.

- [ ] **Step 6: Optional Supabase CLI validation**

If Supabase CLI is configured, run: `supabase db reset`

Expected: migration applies cleanly.

- [ ] **Step 7: Commit**

```bash
git add supabase tests/test_supabase_migration_contract.py
git commit -m "feat: add supabase schema"
```

---

### Task 3: Domain Models And Repositories

**Files:**
- Create: `backend/app/workflows/state.py`
- Create: `backend/app/db/__init__.py`
- Create: `backend/app/db/supabase.py`
- Create: `backend/app/db/repositories.py`
- Test: `tests/test_repositories.py`

- [ ] **Step 1: Write tests for in-memory task persistence**

```python
from backend.app.db.repositories import InMemoryTaskRepository
from backend.app.workflows.state import TaskStatus


def test_task_repository_persists_status_update():
    repo = InMemoryTaskRepository()
    task = repo.create_task(
        original_command="给设备 10086 添加五一广告",
        agent_key="device_ad_agent",
        workflow_key="device_ad_binding",
    )

    repo.update_task_status(task.id, TaskStatus.AWAITING_COMMAND_CONFIRMATION)

    assert repo.get_task(task.id).status == TaskStatus.AWAITING_COMMAND_CONFIRMATION
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_repositories.py -v`

Expected: FAIL because repositories do not exist.

- [ ] **Step 3: Add Pydantic state models**

Include `TaskStatus`, `ApprovalType`, `ApprovalStatus`, `AdvertisementType`, `AdvertisementRequest`, `MatchedAdvertisement`, `DeviceMatch`, `UploadBatch`, and `UploadItem`.

- [ ] **Step 4: Add repository protocols and in-memory implementations**

Implement task, approval, audit, candidate, upload batch, upload item, and local asset candidate repositories.

- [ ] **Step 5: Add Supabase client factory**

`backend/app/db/supabase.py` reads `SUPABASE_URL`, `SUPABASE_ANON_KEY`, and server-only `SUPABASE_SERVICE_ROLE_KEY`. Do not expose service role keys to frontend DTOs.

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_repositories.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/workflows backend/app/db tests/test_repositories.py
git commit -m "feat: add domain models and repositories"
```

---

### Task 4: Permissions And Approval Gates

**Files:**
- Create: `backend/app/safety/__init__.py`
- Create: `backend/app/safety/permissions.py`
- Create: `backend/app/safety/approvals.py`
- Test: `tests/test_safety.py`

- [ ] **Step 1: Write permission tests**

```python
import pytest

from backend.app.safety.permissions import PermissionDenied, PermissionSet


def test_device_agent_cannot_upload_advertisements():
    permissions = PermissionSet.for_device_ad_agent()
    with pytest.raises(PermissionDenied):
        permissions.require("upload_local_asset")


def test_upload_agent_cannot_bind_devices():
    permissions = PermissionSet.for_ad_upload_agent()
    with pytest.raises(PermissionDenied):
        permissions.require("open_device_ad_config")
```

- [ ] **Step 2: Write approval hash tests**

Verify that save approval is valid only when the stored approval hash matches the current pre-save report hash.

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_safety.py -v`

Expected: FAIL because safety modules do not exist.

- [ ] **Step 4: Implement permission sets**

Hardcode v1 whitelists from the spec and keep the shape compatible with DB-loaded permission sets.

- [ ] **Step 5: Implement approval hashing**

Canonicalize JSON payloads with sorted keys, hash with SHA-256, and compare before allowing save.

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_safety.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/safety tests/test_safety.py
git commit -m "feat: enforce permissions and approvals"
```

---

### Task 5: Task Router Agent

**Files:**
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/agents/router.py`
- Test: `tests/test_task_router.py`

- [ ] **Step 1: Write routing tests**

Cover three routing cases:

- device binding command
- advertisement upload command
- mixed upload-and-bind command requiring a two-phase plan

```python
from backend.app.agents.router import TaskRouter, RouteKind


def test_routes_device_binding_command():
    route = TaskRouter().route("给设备 10086 添加五一广告")
    assert route.kind == RouteKind.DEVICE_AD_BINDING
    assert route.target_device_no == "10086"


def test_routes_ad_upload_command():
    route = TaskRouter().route("给企业A的春节标签上传 a.mp4 和 b.jpg")
    assert route.kind == RouteKind.AD_UPLOAD
    assert route.company_query == "企业A"


def test_routes_mixed_command_as_two_phase_plan():
    route = TaskRouter().route("上传五一广告并绑定到设备10086")
    assert route.kind == RouteKind.MIXED_UPLOAD_THEN_BIND
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_task_router.py -v`

Expected: FAIL because router does not exist.

- [ ] **Step 3: Implement deterministic parser**

Use conservative pattern matching for MVP. If required fields are missing, route to a clarification state instead of guessing.

- [ ] **Step 4: Add LLM-ready interface**

Define a `CommandParser` protocol so an LLM parser can replace the deterministic parser later without changing workflows.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_task_router.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/router.py tests/test_task_router.py
git commit -m "feat: add task router"
```

---

### Task 6: Browser Adapter Protocols And Mock Admin

**Files:**
- Create: `backend/app/browser/__init__.py`
- Create: `backend/app/browser/adapters.py`
- Create: `backend/app/browser/mock_admin.py`
- Create: `backend/app/browser/playwright_admin.py`
- Test: `tests/test_mock_admin_adapter.py`

- [ ] **Step 1: Write mock adapter tests**

Test device search, existing ad baseline, ad search by type/category, multi-select safety, company search, tag search, tag creation, and mock upload item save.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_mock_admin_adapter.py -v`

Expected: FAIL because adapters do not exist.

- [ ] **Step 3: Add adapter protocols**

Define `DeviceAdBrowserAdapter` and `AdUploadBrowserAdapter` with exact methods from the spec.

- [ ] **Step 4: Implement `MockAdminAdapter`**

Use in-memory fixtures:

- devices with existing baseline advertisements
- advertisement library with image/video/category fields
- companies and tags
- upload form state and saved advertisements

- [ ] **Step 5: Add guarded Playwright skeleton**

Add method stubs that raise `NotImplementedError` with clear messages. Do not expose arbitrary page click helpers.

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_mock_admin_adapter.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/browser tests/test_mock_admin_adapter.py
git commit -m "feat: add browser adapter contracts"
```

---

### Task 7: Device Advertisement LangGraph Workflow

**Files:**
- Create: `backend/app/workflows/device_ad_graph.py`
- Create: `backend/app/agents/device_ad_agent.py`
- Test: `tests/test_device_ad_workflow.py`

- [ ] **Step 1: Write happy-path workflow test**

Command: bind one known existing advertisement to one known device. Expected final status: `awaiting_save_approval` before approval, then `succeeded` after approval.

- [ ] **Step 2: Write safety branch tests**

Cover:

- device not found
- multiple ads found
- ad missing
- baseline ad removed by page state
- correction can remove only current task unsaved additions
- save blocked before approval

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_device_ad_workflow.py -v`

Expected: FAIL because graph does not exist.

- [ ] **Step 4: Implement graph state**

Include confirmed command, matched device, baseline ads, task-added ads, candidates, pending report, approvals, and audit events.

- [ ] **Step 5: Implement graph nodes**

Nodes:

- parse/confirm command
- check login
- search device
- read baseline
- search ads
- select candidates
- add pending ads
- pre-save verify
- await save approval
- save and report
- correction branch

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_device_ad_workflow.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/workflows/device_ad_graph.py backend/app/agents/device_ad_agent.py tests/test_device_ad_workflow.py
git commit -m "feat: add device advertisement workflow"
```

---

### Task 8: Advertisement Upload Local Asset Services

**Files:**
- Create: `backend/app/assets/__init__.py`
- Create: `backend/app/assets/local_search.py`
- Create: `backend/app/assets/media_validation.py`
- Test: `tests/test_local_assets.py`

- [ ] **Step 1: Write local asset tests**

Use pytest `tmp_path` to create files and test:

- exact filename match
- multiple candidates
- image extension validation
- video extension validation
- media type mismatch rejection

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_local_assets.py -v`

Expected: FAIL because asset modules do not exist.

- [ ] **Step 3: Implement local search**

Search configured base directories only. Return path references and metadata; do not upload or copy files.

- [ ] **Step 4: Implement validation**

Use extension and file metadata where available. Start with conservative extensions from the spec.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_local_assets.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/assets tests/test_local_assets.py
git commit -m "feat: add local asset search"
```

---

### Task 9: Advertisement Upload LangGraph Workflow

**Files:**
- Create: `backend/app/workflows/ad_upload_graph.py`
- Create: `backend/app/agents/ad_upload_agent.py`
- Test: `tests/test_ad_upload_workflow.py`

- [ ] **Step 1: Write upload plan parsing test**

Command contains one company, one tag, two videos, and one image. Expected: one upload batch with three upload items.

- [ ] **Step 2: Write sequential execution test**

Assert only one item can be `uploading` or `awaiting_item_save_approval` at a time.

- [ ] **Step 3: Write tag creation approval test**

If tag is missing, workflow must enter `awaiting_tag_creation_confirmation` and block creation until approved.

- [ ] **Step 4: Write item approval tests**

One item approval saves only that item and never approves another item.

- [ ] **Step 5: Run tests to verify they fail**

Run: `pytest tests/test_ad_upload_workflow.py -v`

Expected: FAIL because upload graph does not exist.

- [ ] **Step 6: Implement upload graph nodes**

Nodes:

- parse upload plan
- await plan confirmation
- check login
- resolve company
- resolve or create tag
- select next pending item
- search local asset
- validate asset
- open create form
- fill metadata
- upload asset
- read preview
- await item save approval
- save item
- summarize batch

- [ ] **Step 7: Implement failure decisions**

Support retry current item, change asset, skip current item, cancel remaining items, and manual takeover.

- [ ] **Step 8: Run tests**

Run: `pytest tests/test_ad_upload_workflow.py -v`

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/workflows/ad_upload_graph.py backend/app/agents/ad_upload_agent.py tests/test_ad_upload_workflow.py
git commit -m "feat: add advertisement upload workflow"
```

---

### Task 10: FastAPI Task And Approval APIs

**Files:**
- Modify: `backend/app/api/schemas.py`
- Modify: `backend/app/api/routes.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_task_api.py`

- [ ] **Step 1: Write API tests**

Cover:

- create task from command
- get task status
- confirm parsed command
- choose candidate
- approve save
- approve tag creation
- approve upload item save

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_task_api.py -v`

Expected: FAIL because APIs are missing.

- [ ] **Step 3: Add request/response schemas**

Use Pydantic models for commands, approvals, candidate decisions, task status, upload batches, and upload items.

- [ ] **Step 4: Implement routes**

Routes:

- `POST /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/events`
- `POST /tasks/{task_id}/approvals/{approval_id}/approve`
- `POST /tasks/{task_id}/approvals/{approval_id}/reject`
- `POST /tasks/{task_id}/candidates/{candidate_id}/select`

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_task_api.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api backend/app/main.py tests/test_task_api.py
git commit -m "feat: add task api"
```

---

### Task 11: Minimal Web Console

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/components/CommandForm.tsx`
- Create: `frontend/src/components/TaskTimeline.tsx`
- Create: `frontend/src/components/ApprovalPanel.tsx`
- Create: `frontend/src/components/CandidateList.tsx`
- Create: `frontend/src/components/UploadItemList.tsx`

- [ ] **Step 1: Scaffold Vite React app files**

Create a small local console. Keep styling functional and low-risk.

- [ ] **Step 2: Add API client**

Implement typed calls for task creation, task polling, approvals, and candidate selection.

- [ ] **Step 3: Add command form**

Allows natural language command input and creates a task.

- [ ] **Step 4: Add task timeline**

Shows audit events and current task status.

- [ ] **Step 5: Add approval panel**

Shows command confirmation, tag creation confirmation, save approval, and upload item save approval.

- [ ] **Step 6: Add upload item list**

Shows item statuses for Advertisement Upload Agent batches.

- [ ] **Step 7: Run frontend checks**

Run: `cd frontend && npm install && npm run build`

Expected: build succeeds.

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -m "feat: add local web console"
```

---

### Task 12: End-To-End Mock Scenario Tests

**Files:**
- Create: `tests/test_e2e_mock_scenarios.py`

- [ ] **Step 1: Write device binding e2e test**

Use FastAPI `TestClient` and mock repositories/adapters. Create a task, confirm command, approve save, assert succeeded and audit events exist.

- [ ] **Step 2: Write advertisement upload e2e test**

Use tmp local assets. Create upload command with two items, confirm plan, approve first item, approve second item, assert batch completed.

- [ ] **Step 3: Write mixed workflow e2e test**

Command asks upload then bind. Assert upload phase completes first and device binding requires a separate owner confirmation before starting.

- [ ] **Step 4: Run e2e tests**

Run: `pytest tests/test_e2e_mock_scenarios.py -v`

Expected: PASS.

- [ ] **Step 5: Run full backend suite**

Run: `pytest -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_e2e_mock_scenarios.py
git commit -m "test: add mock e2e scenarios"
```

---

### Task 13: Playwright Adapter Readiness

**Files:**
- Modify: `backend/app/browser/playwright_admin.py`
- Create: `docs/integration/real-backend-checklist.md`
- Test: `tests/test_playwright_adapter_guardrails.py`

- [ ] **Step 1: Write guardrail tests**

Assert the Playwright adapter exposes only whitelisted business methods and no arbitrary click/type method.

- [ ] **Step 2: Add persistent browser profile config**

Read a local profile path or alias from settings. Do not store cookies or backend credentials in Supabase.

- [ ] **Step 3: Add login check skeleton**

Implement `check_login()` with selector configuration stubs and clear `NotImplementedError` for unknown selectors.

- [ ] **Step 4: Add integration checklist**

Document required real backend inputs:

- backend URL
- test company
- test tags
- test device
- test image/video ads
- selectors/menu paths
- staging vs production rules

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_playwright_adapter_guardrails.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/browser/playwright_admin.py docs/integration tests/test_playwright_adapter_guardrails.py
git commit -m "chore: prepare playwright adapter guardrails"
```

---

### Task 14: Documentation And Runbook

**Files:**
- Create: `README.md`
- Create: `docs/runbooks/local-development.md`
- Create: `docs/runbooks/supabase-setup.md`
- Create: `docs/runbooks/safety-model.md`

- [ ] **Step 1: Document local setup**

Include Python setup, frontend setup, Supabase env vars, and mock mode.

- [ ] **Step 2: Document safety model**

Explain agent boundaries, approval gates, baseline ad protection, tag creation confirmation, and upload item sequential execution.

- [ ] **Step 3: Document verification commands**

Commands:

```bash
pytest -v
cd frontend && npm run build
```

- [ ] **Step 4: Run verification**

Run backend and frontend verification commands.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md docs/runbooks
git commit -m "docs: add development runbooks"
```

---

## Milestone Verification

After Task 12, the project should support complete mock-mode flows:

- natural language command routed to the correct agent
- device advertisement binding pauses for command and save approvals
- baseline advertisements are protected
- advertisement upload batches are split into sequential items
- missing tags require owner approval before creation
- local asset ambiguity pauses for owner selection
- every save is owner-approved
- audit events are written

After Task 14, the project should be ready for real backend selector discovery.

Run:

```bash
pytest -v
cd frontend && npm run build
git status --short
```

Expected:

- all backend tests pass
- frontend builds successfully
- working tree is clean
