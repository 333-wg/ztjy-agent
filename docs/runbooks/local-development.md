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

The default app uses in-memory repositories and `MockAdminAdapter`. Restarting the server resets tasks, approvals, mock devices, mock ads, and upload state.

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
