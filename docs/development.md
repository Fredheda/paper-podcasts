# Development

How to run Paper Podcasts locally, run the checks, and make a change.

## Prerequisites

- Python 3.13 (pinned by `.python-version`), managed with Poetry (`pyproject.toml` and `poetry.lock`). There is no `requirements.txt`.
- Node.js 18+
- An OpenAI API key. OpenAI is the only LLM and text-to-speech provider.

## Environment variables

Create a `.env` file in the repo root. Only `OPENAI_API_KEY` is required locally.

```bash
OPENAI_API_KEY=your_key
```

Optional settings, all read by the backend:

| Variable | Default | Purpose |
|---|---|---|
| `STORAGE_BACKEND` | `local` | `local` (filesystem and SQLite, no Azure setup) or `azure` (Blob Storage and Azure SQL). |
| `AZURE_STORAGE_ACCOUNT`, `AZURE_SQL_SERVER`, `AZURE_SQL_DATABASE`, `AZURE_CLIENT_ID` | none | Required when `STORAGE_BACKEND=azure`. |
| `BACKEND_API_KEY` | unset | When set, non-health endpoints require it in the `x-api-key` header. |
| `RATE_LIMIT_PER_MINUTE` | `120` | Per-client limit on non-health routes. |
| `FORCE_HTTPS` | `false` | Require HTTPS and send the HSTS header. |
| `TRUST_PROXY_HEADERS` | `false` | Trust `x-forwarded-proto`. Enable only behind a trusted proxy. |

The frontend reads `VITE_API_BASE_URL`, which defaults to an empty string (same-origin relative paths). Set it only if the backend ever lives on a different origin. Never put backend secrets in frontend environment variables.

## Install

```bash
poetry install --with backend,dev   # `dev` brings in honcho and pytest
cd frontend && npm install
```

## Run

```bash
poetry run honcho start   # backend and frontend together, via the repo-root Procfile
```

The backend listens on http://127.0.0.1:8000 and the frontend on http://localhost:5173. Use `localhost`, not `127.0.0.1`: the Vite dev config binds to the hostname. Ctrl+C once stops both.

To run them separately, from the repo root:

```bash
poetry run uvicorn backend.app.main:app --reload --port 8000
cd frontend && npm run dev
```

There is no CORS middleware, because the browser never talks to the backend directly. In production the web container proxies `/api/*` and `/health` to the backend (`frontend/server.js`). In local development the `server.proxy` setting in `frontend/vite.config.ts` does the same.

## Backend API

The routes are in `backend/app/routes/`: `/health`, search and the job queue (`/api/search`, `/api/jobs/enqueue`, `/api/jobs`), the library (`/api/library` and its `content`, `audio` and `listen` sub-routes) and paper chat (`/api/chat/stream`).

## Checks

Backend, from the repo root:

```bash
poetry run pytest -v      # offline, local storage backend
poetry run ruff check . && poetry run ruff format --check .
poetry run pyright
```

Frontend, from `frontend/`:

```bash
npm test          # vitest
npm run lint      # eslint
npm run build     # tsc -b && vite build, which is also the type check
```

`./scripts/ci-local.sh` runs all of the above in the order CI does. CI (`.github/workflows/ci.yml`) runs them on pull requests only, as three jobs: `backend`, `frontend` and `frontend-build` (skipped on drafts and, with the others, on docs-only changes).

## Making a change

1. Edit the right layer: pipeline logic in `src/`, the API in `backend/app/`, the UI in `frontend/src/`.
2. Run the checks above, then `poetry run honcho start` and try the change at http://localhost:5173.
3. Commit and open a pull request. To ship it to Azure, see [deployment](../deployment/README.md).
