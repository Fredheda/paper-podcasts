# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start Commands

One app (`backend/` FastAPI + `frontend/` React/Vite) wraps the shared
pipeline (`src/`). Dependencies are managed by Poetry (`pyproject.toml` +
`poetry.lock`, Python 3.13 pinned by `.python-version`) — there is no
`requirements.txt` anywhere in this repo.

### Install
```bash
poetry install --with backend,dev   # `main` alone covers just the shared pipeline; `dev` brings in honcho (below) and pytest
cd frontend && npm install
```

### Run
```bash
poetry run honcho start   # both backend + frontend from one command, via the repo-root Procfile
```
Backend on http://127.0.0.1:8000, frontend on http://localhost:5173 (note: `localhost`, not `127.0.0.1` — Vite's dev config binds to the hostname specifically). Ctrl+C once stops both.

Equivalent two-terminal version, if you want them separate:
```bash
poetry run uvicorn backend.app.main:app --reload --port 8000   # backend, from repo root
cd frontend && npm run dev                                      # frontend, separate terminal
```
Backend architecture, endpoints, and security config are documented in `backend/README.md` — don't duplicate that here, read it directly.

### Environment Setup
Create a root `.env` file with:
```
OPENAI_API_KEY=your_key_here
```

## Architecture Overview

### Core Pipeline Architecture

This is a **state machine-driven paper processing pipeline** that transforms academic papers into audio podcasts through four sequential stages. The architecture is designed for robustness, resumability, and clear separation of concerns.

#### State Machine Flow
The pipeline uses `python-statemachine` to ensure valid state transitions and process integrity:

```
new → downloading → downloaded → extracting → extracted →
summarizing → summarized → generating_audio → audio_generated → completed
```

Any stage can transition to `failed` state on error. The state machine is defined in `src/pipeline/paper_workflow.py` and provides:
- **Idempotent operations**: Can't download/extract/summarize the same paper twice
- **Resume capability**: Can restart from any stable state (downloaded, extracted, summarized)
- **Audit trail**: All state transitions are logged

#### Service Layer Architecture

The pipeline (`PaperPipeline` in `src/pipeline/paper_pipeline.py`) orchestrates four independent services:

1. **ArxivService** (`src/services/arxiv_service.py`): Searches and downloads papers from arXiv
2. **PdfService** (`src/services/pdf_service.py`): Extracts content from PDFs using `markitdown`
3. **LLMService** (`src/services/llm_service.py`): Generates summaries using LLM providers
4. **AudioService** (`src/services/audio_service.py`): Converts text to speech using TTS providers

Each service is **provider-agnostic** through abstract base classes:
- `LLMProvider` (currently: `OpenAIProvider`)
- `TTSProvider` (currently: `OpenAITTSProvider`)

This allows swapping providers without changing pipeline logic.

#### Data Model Architecture

All data models are in `src/models/`:

- **Paper** (`paper.py`): Central model with metadata, state tracking, and listen status. Handles filename sanitization via `cleaned_title` property.
- **Result objects**: Each pipeline stage returns a specific result object:
  - `DownloadResult`: PDF path and metadata
  - `ExtractionResult`: Contains `ExtractedContent` with markdown text
  - `SummaryResult`: Summary text and save location
  - `AudioResult`: Audio file path and duration
  - `PipelineResult`: Aggregates all stage results

Paper artifacts (PDF, extracted text, summary, audio) and metadata (status,
listen state) go through two interfaces — `ArtifactStore` and
`MetadataStore` (`src/services/artifact_store.py`,
`src/services/metadata_store.py`) — selected once in `backend/app/state.py`
via `STORAGE_BACKEND`:

- `local` (default): `LocalFileStorageService` (plain filesystem, rooted at
  `data/papers/`) + `SqliteMetadataService` (`data/podcasts.db`, stdlib
  `sqlite3`, zero setup — the table is created on first use).
- `azure`: `BlobStorageService` (Azure Blob Storage) +
  `AzureSqlMetadataService` (Azure SQL).

`paper_state.json` is retired — there is no on-disk metadata file anymore,
only the artifact files themselves. See
`docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md` (workspace root) for
the full design. A one-time script, `scripts/migrate_local_json_to_sqlite.py`,
migrated this repo's pre-existing local library from `paper_state.json`
files into `data/podcasts.db`; there's no reason to run it again unless
you're restoring from an old backup that still has `paper_state.json` files.

#### Storage Structure

```
data/papers/<cleaned_title>/
├── <paper>.pdf               # Downloaded PDF
├── extracted/
│   └── <paper>.md           # Extracted markdown
├── summaries/
│   └── summary_<paper>.txt  # LLM-generated summary
└── audio/
    └── <paper>.mp3          # TTS-generated audio
data/podcasts.db              # SQLite metadata store (STORAGE_BACKEND=local)
```

### Key Design Patterns

1. **Lazy Loading**: Pipeline stages load previous results from disk only when needed, allowing partial pipeline runs (e.g., only audio generation)

2. **State Persistence**: The `Paper` model syncs its `status` field with the state machine via `state_field="status"` parameter

3. **Progressive Processing**: Each stage checks `can_<action>()` methods before execution, preventing invalid operations

4. **Provider Pattern**: Services use dependency injection with provider interfaces for extensibility

### Backend Architecture (`backend/`)

FastAPI service wrapping the shared pipeline for the React frontend, with background job processing: `ProcessingManager` (`src/services/processing_manager.py`) runs a multi-worker queue, and the frontend polls `GET /api/jobs` for live status. Full module breakdown, endpoints, and request flow are in `backend/README.md` — read that instead of duplicating it here.

### Prompt System

LLM prompts live in `prompts/` directory:
- `summarize_paper.txt`: Template for generating audio-friendly summaries
- Uses string `.format()` with placeholders: `{paper_content}`, `{title}`, `{authors}`, `{published}`
- Prompts specify HTML output format, parsed and rendered by the frontend (`frontend/src/App.tsx`)

## Important Implementation Details

### Paper Identification
- Papers are identified by `cleaned_title` (not `arxiv_id`) for directory naming
- `arxiv_id` has version suffix stripped in `__post_init__`
- The `clean_filename()` static method sanitizes titles for filesystem use (max 200 chars)

### State Machine Integration
When modifying the pipeline:
- Always update `paper.status` through state machine transitions (e.g., `workflow.complete_download()`)
- Call `_save_paper_state(paper)` after each stage to persist state
- Check `workflow.can_<action>()` before attempting transitions

### Provider Implementation
To add a new LLM or TTS provider:
1. Create provider class in `src/services/llm_providers.py` or `tts_providers.py`
2. Inherit from `LLMProvider` or `TTSProvider` abstract base class
3. Implement required methods (`generate()` for LLM, `text_to_speech()` for TTS)
4. Update service initialization in `backend/app/state.py`

### Listen Status Tracking
Papers track whether they've been listened to:
- `listen_status`: "unlistened" or "listened"
- `last_listened_at`: Timestamp of last listen
- Persisted via `state.metadata_service.update_listen_status(arxiv_id, listen_status, last_listened_at)`, called from `POST /api/library/{arxiv_id}/listen` (`backend/app/routes/library.py`) — not a `Paper` instance method.

This is independent of processing status and used for library filtering in the UI.

## Deployment (Azure Container Apps)

Live at [podcasts.frederikheda.com](https://podcasts.frederikheda.com) — a
custom domain bound to `ca-podcasts-web` with a free Azure-managed TLS
certificate. The default `*.azurecontainerapps.io` URL also works (both are
registered Easy Auth redirect URIs). Prod runs as two consumption-plan
container apps in `rg-chatbot` / `cae-podcasts` (westeurope), images in ACR
(`acrchatbotfredheda.azurecr.io`, shared with `copilot-kit-exp` and
`Portfolio`), built with `scripts/build-push.sh` (`az acr build`, no CI, no
stored registry credentials) and pulled via a user-assigned managed identity
(`id-podcasts-acrpull`, AcrPull + Storage Blob Data Contributor scoped to the
`paper-podcasts` blob container). Infra is defined in `infra/main.bicep` and
deployed with `infra/deploy.sh`.

- `ca-podcasts-agent` — FastAPI backend, **internal ingress only** (never
  externally reachable — only `ca-podcasts-web` has external ingress), port
  8000, `STORAGE_BACKEND=azure` (reuses Portfolio's `fhstorageportfolio`
  storage account and `fhdbplayground`/`PlaygroundDB` SQL server —
  see `docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md`). Local dev
  defaults to `STORAGE_BACKEND=local` (filesystem + SQLite, zero Azure setup).
- `ca-podcasts-web` — React/Vite SPA behind a small Express `server.js`,
  external ingress, port 3000, proxies `/api/*` and `/health` to the
  internal backend. Protected by Easy Auth (Entra app `podcasts-easyauth`,
  assignment required), configured via `scripts/setup-easyauth.sh` — which
  registers redirect URIs for both the custom domain and the default FQDN.

Workflows: provision or change infra with `infra/deploy.sh [tag]`. Steady
state (code changes): `scripts/ship.sh` (build+push then roll both apps;
needs a clean tree + `az login`). Grant access with
`scripts/approve-user.sh <email>`. Both apps scale to zero
(`minReplicas: 0`) — first request after idle takes ~15–40s. A replica dying
mid-processing loses only that in-flight stage's LLM/TTS spend; re-triggering
resumes from the last durably-saved stage (see the spec's "Error handling").
The environment omits `appLogsConfiguration` (no Log Analytics meter); live
logs via `az containerapp logs show --follow`. See `DEPLOYMENT.md` for the
step-by-step change workflow and `EXPIRATIONS.md` for renewal reminders.

# Fred's Personal Claude Preferences


## MCP Servers

### Context7
  - You have access to context7 which provides access to up-to-date documentation. Use it often, whenever it might be helpful.