# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> This repo lives inside a multi-repo workspace with its own root `CLAUDE.md`
> (`../CLAUDE.md`, one level up) covering workspace-wide conventions — where
> specs/plans go, the git rule, shared MCP/skill usage. Keep that
> file's per-project facts about this repo (test-suite status, architecture
> pointers, etc.) in sync whenever they drift from what's true here.

**Git:** you may run git freely up to a commit, and push a feature branch and
open a PR. `fetch` and `pull` are fine too (default to `pull --ff-only`). Ask
first for `rebase`, `reset`, force-push, deleting branches, or anything on
`main`. Reviewing and merging PRs is the user's alone — hand over the PR URL.
Other Claude sessions share this workspace: work in your own git worktree,
never the main checkout. Create one with `git worktree add
../.worktrees/<repo>-<slug> -b <branch> origin/main` (or the `EnterWorktree`
tool) and remove it after the PR merges; details in the "Parallel sessions"
section of the root `CLAUDE.md`. Commit messages are 2 lines at most, with no
`Co-Authored-By` trailer. Full rule in the root `CLAUDE.md` linked above.
PR titles and descriptions must not mention Claude Code or link the Claude
session (no "Generated with Claude Code" footer).
After opening a PR, wait for CI to pass (`gh pr checks --watch`), then read the
LLM review comments and address them, before handing the PR URL over for review.

**Response style:** use the `caveman` skill for responses in this repo —
invoke it before replying, not just when asked.

## Where to look

- Run, test and env vars: [`docs/development.md`](docs/development.md)
- Deploying, operating, expiries: [`deployment/`](deployment/README.md)
- Overview for readers: [`README.md`](README.md)

## Commands

One app (`backend/` FastAPI + `frontend/` React/Vite) wraps the shared pipeline (`src/`). Poetry only, Python 3.13; there is no `requirements.txt`. Run from the repo root so `src/`, `prompts/`, `data/` and the root `.env` resolve.

```bash
poetry install --with backend,dev && (cd frontend && npm install)
poetry run honcho start                       # backend :8000 + frontend :5173 (use localhost, not 127.0.0.1)
poetry run pytest -v                          # offline
poetry run ruff check . && poetry run ruff format --check . && poetry run pyright
cd frontend && npm test && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs all of this on every PR and push to `main`: `backend-test`, `backend-lint`, `frontend-test`, `frontend-checks`. `.github/workflows/claude-review.yml` posts an AI security review on PRs and on pushes; the owner can also request one by commenting `@claude` (comment-only; the `CLAUDE_CODE_OAUTH_TOKEN` secret expires about 2027-10-24, see `deployment/expirations.md`). Its prompt says `frontend/.env.production` is tracked on purpose; update the prompt if that file ever holds a secret.

Dependabot (`.github/dependabot.yml`) opens weekly version-update PRs, labelled `dependencies`, for `pip` (Poetry, `/`), `npm` (`/frontend`), `github-actions` and the two Dockerfiles (`/backend`, `/frontend`); `cooldown: default-days: 14` holds back versions younger than two weeks. Dependabot alerts and automatic security-update PRs are repo settings, not files. The AI review skips Dependabot PRs.

Env vars: `OPENAI_API_KEY` (required, OpenAI is the only provider); `STORAGE_BACKEND` (`local` default, or `azure` with `AZURE_STORAGE_ACCOUNT`, `AZURE_SQL_SERVER`, `AZURE_SQL_DATABASE`, `AZURE_CLIENT_ID`); `BACKEND_API_KEY`, `RATE_LIMIT_PER_MINUTE`, `FORCE_HTTPS`, `TRUST_PROXY_HEADERS`. Defaults in `docs/development.md`.

## Pipeline

`PaperPipeline` (`src/pipeline/paper_pipeline.py`) runs four services in order: `ArxivService`, `PdfService` (`markitdown`), `LLMService`, `AudioService`. LLM and TTS go through `LLMProvider` / `TTSProvider` abstract classes (only OpenAI implementations exist). To add a provider: subclass in `src/services/llm_providers.py` or `tts_providers.py`, implement `generate()` / `text_to_speech()`, and wire it in `backend/app/state.py`.

The status state machine (`python-statemachine`, `src/pipeline/paper_workflow.py`) goes `new → downloading → downloaded → extracting → extracted → summarizing → summarized → generating_audio → audio_generated → completed`, and any stage can go to `failed`. When changing the pipeline:

- Move `paper.status` only through workflow transitions (e.g. `workflow.complete_download()`), and check `workflow.can_<action>()` first.
- Call `_save_paper_state(paper)` after each stage.
- Stages load earlier results lazily, so partial runs (audio only) and resuming from a stable state work.

## Storage

`ArtifactStore` and `MetadataStore` (`src/services/artifact_store.py`, `metadata_store.py`) are chosen once in `backend/app/state.py` by `STORAGE_BACKEND`: `local` is `LocalFileStorageService` (`data/papers/`) plus `SqliteMetadataService` (`data/podcasts.db`, table created on first use); `azure` is `BlobStorageService` plus `AzureSqlMetadataService`.

- Artifacts are always written to local disk first, then persisted through the store (a no-op for `local`, a Blob upload for `azure`). The container disk is ephemeral, so Blob Storage is what survives there.
- Per-paper layout: `data/papers/<cleaned_title>/` holds the PDF, `extracted/<paper>.md`, `summaries/summary_<paper>.txt` and `audio/<paper>.mp3`.
- `paper_state.json` is retired. `scripts/migrate_local_json_to_sqlite.py` was a one-time migration; rerun it only when restoring an old backup that still has `paper_state.json` files.

## Gotchas

- Papers are identified on disk by `cleaned_title`, not `arxiv_id`. `arxiv_id` has its version suffix stripped in `__post_init__`; `clean_filename()` caps titles at 200 chars.
- Listen state (`listen_status` "unlistened" / "listened", `last_listened_at`) is persisted by `state.metadata_service.update_listen_status(...)` from `POST /api/library/{arxiv_id}/listen`, not by a `Paper` method. It is independent of processing status.
- No CORS middleware, on purpose: the browser only talks to its own origin, and `frontend/server.js` (prod) or `server.proxy` in `frontend/vite.config.ts` (dev) proxies `/api` and `/health`. Prod backend has internal ingress only.
- Prompts in `prompts/` use `.format()` placeholders (`summarize_paper.txt`: `{paper_content}`, `{title}`, `{authors}`, `{published}`). The summary prompt asks for HTML, which `frontend/src/App.tsx` renders.
- Frontend polling pauses after `IDLE_PAUSE_MS` (60s) with no active job so the container apps can scale to zero. Do not remove it.
- Deploy: `scripts/ship.sh` refuses a dirty tree on purpose (an unchanged image tag can keep serving the old revision). First request after idle is slow, and the shared serverless SQL DB can return transient 500s after a pause. Both explained in `deployment/local.md` and `deployment/operations.md`.
- Specs and plans for this repo are in the workspace-root `docs/paper-podcasts/` (the 2026-08-15 deployment spec and plan hold the design).
