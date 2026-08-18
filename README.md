# Paper Podcasts

Paper Podcasts turns arXiv papers into summaries and audio: search arXiv,
enqueue papers, and get back a rich summary plus a generated audio version,
backed by a state-machine-driven processing pipeline.

Live at [podcasts.frederikheda.com](https://podcasts.frederikheda.com)
(Easy Auth gated). See `CLAUDE.md`'s "Deployment (Azure Container Apps)"
section and `DEPLOYMENT.md` for how that's run.

## Repository Layout

- `src/`: shared domain models, services, and pipeline
- `prompts/`: shared LLM prompts
- `data/`: local runtime artifacts (state, extracted text, summaries, audio)
  — only used when `STORAGE_BACKEND=local` (the default for local dev)
- `assets/`: static images/diagrams
- `backend/`: FastAPI API server
- `frontend/`: React + TypeScript + Tailwind UI

There is no legacy Streamlit UI anymore — it was removed once the
FastAPI + React app reached feature parity; `backend/` + `frontend/` is the
only app.

## Prerequisites

- Python 3.13 (pinned by `.python-version`), managed via Poetry (`pyproject.toml` + `poetry.lock`)
- Node.js 18+
- API key: `OPENAI_API_KEY` (OpenAI only — no other LLM provider is used)

Create a root `.env` file:

```bash
OPENAI_API_KEY=your_key
```

## Run

```bash
poetry install --with backend,dev
cd frontend && npm install && cd ..
poetry run honcho start   # backend + frontend together, via the repo-root Procfile
```

Backend on `http://127.0.0.1:8000`, frontend on `http://localhost:5173`
(note: `localhost`, not `127.0.0.1` — Vite's dev config binds to the
hostname specifically). Ctrl+C once stops both. See `CLAUDE.md`'s "Quick
Start Commands" for the two-terminal alternative if you want the servers
separate, and `backend/README.md` / `frontend/README.md` for
per-app detail.

`STORAGE_BACKEND` defaults to `local` (filesystem + SQLite, zero Azure setup
needed) — the same code path production runs, just backed by
`azure` (Blob Storage + Azure SQL) there instead. See
`docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md`
(workspace root) for the full design.

## Core Capabilities

- Search papers on arXiv
- Enqueue processing jobs with concurrent workers (up to configured limit) and queue overflow
- Track live job status/progress
- Browse processed library with filters
- Rich summary rendering per paper, auto-fetched as it appears in the
  library (no separate "view" step); reading the full paper happens via
  "Open on arXiv", not an in-app viewer
- Play generated audio and mark listened/unlistened

## Notes

- Artifacts are always written to local disk first, then durably persisted
  through the active `ArtifactStore` on top of that — a same-path no-op for
  `local`, an actual Blob Storage upload for `azure`. See `backend/README.md`
  for the full explanation (this matters because the deployed container's
  local disk is ephemeral; Blob Storage is what actually survives there).
- Backend security controls (optional API key, rate limiting, HTTPS
  controls) are documented in `backend/README.md`. There is no CORS
  middleware — see that file's "No CORS middleware" note for why.
