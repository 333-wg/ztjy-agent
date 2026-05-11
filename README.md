# Advertisement Agent System

Local-first agent system for controlled browser automation of a company management backend.

The current build runs in mock mode. It supports:

- natural-language task creation through FastAPI
- deterministic routing to device advertisement binding or advertisement upload workflows
- LangGraph-backed workflow steps for device binding and upload item processing
- owner approval gates before save actions
- add-only device advertisement binding that preserves baseline ads
- sequential advertisement upload items with local asset validation
- Supabase schema and seed files for production-aligned persistence
- a Vite React local console for task creation, approvals, candidates, upload items, and audit events

## Quick Start

Backend:

```powershell
uv run uvicorn backend.app.main:create_app --factory --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Verification:

```powershell
uv run pytest -v
cd frontend
npm run build
```

## Real Backend Status

The Playwright adapter is intentionally guarded. It exposes business methods only, with no arbitrary `click`, `type`, or `evaluate` helpers. Real backend selector discovery must follow [real-backend-checklist.md](docs/integration/real-backend-checklist.md).

## Safety Defaults

- No backend credentials are stored by the app.
- Device binding cannot upload or create ads.
- Upload workflow cannot bind ads to devices.
- Final save requires an approved hash-matched report.
- Mixed upload-then-bind commands pause for separate owner confirmation before handoff.
