# Backend

FastAPI service for search, processing queue orchestration, and library access.

## Setup

From repo root:

```bash
poetry install --with backend
poetry run uvicorn backend.app.main:app --reload --port 8000
```

The backend loads environment variables from the repo root `.env`.

## Shared Paths

- Shared pipeline code: `src/`
- Prompts: `prompts/`
- Runtime artifacts: `data/`

No CORS middleware: the browser never talks to this backend directly, in
prod or in local dev. In prod, `ca-podcasts-agent` is **internal ingress
only** and reached exclusively via `ca-podcasts-web`'s Express `server.js`,
which proxies `/api/*` server-side. In local dev, `frontend/vite.config.ts`'s
`server.proxy` does the same thing for the Vite dev server — so the browser
only ever talks to whichever server is serving the frontend, same-origin,
in both cases.

## Security Config

- `BACKEND_API_KEY`: optional API key for non-health endpoints (`x-api-key`)
- `RATE_LIMIT_PER_MINUTE`: per-client limit for non-health routes
  - Default: `120`
- `FORCE_HTTPS`: require HTTPS and emit HSTS header
  - Default: `false`
- `TRUST_PROXY_HEADERS`: trust `x-forwarded-proto` (enable only behind trusted proxy)
  - Default: `false`
- `STORAGE_BACKEND`: `local` (default — filesystem + SQLite, zero Azure
  setup, table created on first use) or `azure` (Blob Storage + Azure SQL —
  requires `AZURE_STORAGE_ACCOUNT`, `AZURE_SQL_SERVER`, `AZURE_SQL_DATABASE`,
  and `AZURE_CLIENT_ID` set — see
  `docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md` at the workspace root)

## API Endpoints

- `GET /health`
- `POST /api/search`
- `POST /api/jobs/enqueue`
- `GET /api/jobs`
- `GET /api/library`
- `GET /api/library/{arxiv_id}/content`
- `GET /api/library/{arxiv_id}/audio`
- `POST /api/library/{arxiv_id}/listen`

## Notes

- Processing is handled by a background `ProcessingManager` with multi-worker concurrency.
- Artifacts are persisted to disk and survive restarts.

## Architecture

The backend is split into small modules so responsibilities are explicit:

- `app/main.py`: app assembly only (create app, attach middleware, include routers)
- `app/config.py`: environment loading, path bootstrap, shared config constants
- `app/state.py`: startup/shutdown lifecycle and long-lived service initialization
- `app/security.py`: CORS setup plus HTTPS/API-key/rate-limit middleware
- `app/mappers.py`: API schema <-> domain model conversion helpers
- `app/arxiv_ids.py`: shared arXiv ID normalization
- `app/routes/health.py`: liveness endpoint
- `app/routes/jobs.py`: search, enqueue, and queue status endpoints
- `app/routes/library.py`: library list/content/audio/listen-status endpoints

### Request Flow (High Level)

1. Request enters FastAPI app (`main.py`).
2. Security middleware runs (`security.py`).
3. Matching router handles the endpoint (`routes/*`).
4. Route uses shared initialized services from `state.py` and shared logic in `src/`.
5. For library reads/writes, routes call `state.metadata_service`/`state.blob_service`
   (the `ArtifactStore`/`MetadataStore` pair selected once at startup by
   `STORAGE_BACKEND` — see `src/services/artifact_store.py` and `metadata_store.py`).
