# Local Development Runbook

## Backend

Install dependencies and run tests:

```powershell
uv run pytest -v
```

Run the FastAPI mock backend:

```powershell
uv run uvicorn backend.app.main:create_app --factory --reload --port 8000
```

The default app uses in-memory repositories, an in-memory LangGraph checkpointer, and `MockAdminAdapter`.
Restarting the server resets tasks, approvals, mock devices, mock ads, upload state, and in-memory checkpoints.

LangGraph checkpointing is enabled by default for local multi-turn workflow state:

```text
LANGGRAPH_CHECKPOINTER=memory
```

Use `LANGGRAPH_CHECKPOINTER=none` only for tests or one-off debugging where resume state is not needed.

## LLM Command Parsing

Local development defaults to deterministic parsing:

```text
LLM_PARSER_MODE=deterministic
LLM_PROVIDER=none
```

To test an OpenAI-compatible model gateway for natural-language command parsing:

```text
LLM_PARSER_MODE=hybrid
LLM_PROVIDER=openai_compatible
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=
LLM_TEMPERATURE=0
LLM_TIMEOUT_SECONDS=30
```

`hybrid` mode tries the deterministic parser first and calls the model only when the command needs clarification. The model only returns structured routing fields; workflow safety gates and browser permissions still enforce the allowed actions.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/tasks` and `/health` to `http://127.0.0.1:8000`.

Build check:

```powershell
cd frontend
npm run build
```

## Useful Mock Commands

Device binding:

```text
给设备 10086 添加 May promo video
```

Ad upload with existing tag:

```text
给企业A的Existing标签上传 a.mp4 b.jpg
```

Ad upload with missing tag:

```text
给企业A的Spring标签上传 a.mp4
```

Mixed flow:

```text
给企业A的Existing标签上传 a.mp4 并绑定到设备 10086
```
