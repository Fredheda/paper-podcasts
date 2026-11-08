# CLAUDE.md

Repo-specific facts. Everything else (style, git, workflow, tooling, Jira, specs and plans) is in the workspace `CLAUDE.md` (`../CLAUDE.md`).

PR titles and descriptions never mention Claude Code. `./scripts/ci-local.sh` runs every `ci.yml` check in CI order (a test keeps them in step); run it green before `gh pr ready`.

## Where to look

- Run, test and env vars: [`docs/development.md`](docs/development.md)
- Deploying, operating, expiries: [`deployment/`](deployment/README.md)
- Overview for readers: [`README.md`](README.md)
- Specs and plans: workspace-root `docs/paper-podcasts/` (the 2026-08-15 deployment spec and plan hold the design).

## Commands

One app (`backend/` FastAPI + `frontend/` React/Vite) wraps the shared pipeline (`src/`). Poetry only, Python 3.13; there is no `requirements.txt`. Run from the repo root so `src/`, `prompts/`, `data/` and the root `.env` resolve.

```bash
poetry install --with backend,dev && (cd frontend && npm install)
poetry run honcho start                       # backend :8000 + frontend :5173 (use localhost, not 127.0.0.1)
poetry run pytest -v                          # offline
poetry run ruff check . && poetry run ruff format --check . && poetry run pyright
cd frontend && npm test && npm run lint && npm run build
```

Tests: unit tests for logic, offline integration tests at the factory seams (`backend/app/state.py`), one e2e per user-visible flow, no duplicate coverage.

CI (`.github/workflows/ci.yml`) runs on pull requests only, never on a push to `main`: `backend` (ruff, pyright, pytest), `frontend` (lint, tests) and `frontend-build`, which skips drafts. Docs-only changes (Markdown or `docs/`) skip all three. `.github/workflows/claude-review.yml` runs on ready PRs (not drafts, not Dependabot) and on every push to them: an AI security review, a documentation check ("Docs: current" or a finding) and advisory size and tests checks ("Size: OK", "Tests: OK" or a finding). A `@claude` comment by the owner requests one (comment-only). The `CLAUDE_CODE_OAUTH_TOKEN` secret expires about 2027-10-24 (`deployment/expirations.md`).

`frontend/.env.production` is tracked on purpose: it holds only the public, empty `VITE_API_BASE_URL`, so the SPA calls its own origin. `.gitignore` covers the other env, key and state files (`.env*`, `*.pem`, `*.key`, `local.settings.json`, `terraform.tfstate`, `.azure/`), and the review prompt says not to flag that file. Update both if it ever holds a secret.

- **Merging:** the owner merges, except the bot and docs classes in the workspace `CLAUDE.md` (Git), which the coordinator merges.

Dependabot (`.github/dependabot.yml`) opens weekly PRs labelled `dependencies` for `pip` (Poetry, `/`), `npm` (`/frontend`), `github-actions` and the two Dockerfiles (`/backend`, `/frontend`). `cooldown: default-days: 14` holds back versions younger than two weeks. Minor and patch updates are grouped into one PR per ecosystem per run. Pip majors are separate PRs; npm majors are ignored (they need code changes, done by hand). Base images: Node majors (frontend) and Python majors and minors (backend, pinned to 3.13) are ignored; patches arrive. Dependabot alerts and security-update PRs are repo settings, not files.

Security (`.github/workflows/security.yml`, each job commented) runs on pull requests, weekly and on demand (`gh workflow run security.yml --ref main`), never on a merge to `main`. Required on `main` (ruleset id 11380504, file `.github/rulesets/main-protect.json`): `backend`, `frontend`, `frontend-build`, `gitleaks`, `workflow-lint`, `bandit`. `tests/test_ruleset.py` pins them to the job ids: rename no job without the file. Apply a ruleset change only on the owner's yes (a repo setting): `gh api -X PUT repos/Fredheda/paper-podcasts/rulesets/11380504 --input .github/rulesets/main-protect.json`. `gitleaks`, `workflow-lint` and `bandit` block. `pip-audit` and `npm-audit` are advisory on PRs and fail the weekly run. `codeql` reports to the Security tab. Locally: `gitleaks git . --redact`, `actionlint`, `pipx run bandit==1.9.4 -r src backend scripts -lll`, `poetry run pip-audit --local --ignore-vuln PYSEC-2026-2275` (dated ignore, see `deployment/expirations.md`), `cd frontend && npm audit --omit=dev --audit-level=high`.

Env vars: `OPENAI_API_KEY` (required, OpenAI is the only provider); `STORAGE_BACKEND` (`local` default, or `azure` with `AZURE_STORAGE_ACCOUNT`, `AZURE_SQL_SERVER`, `AZURE_SQL_DATABASE`, `AZURE_CLIENT_ID`); `BACKEND_API_KEY`, `RATE_LIMIT_PER_MINUTE`, `FORCE_HTTPS`, `TRUST_PROXY_HEADERS`. Defaults in `docs/development.md`.

## Pipeline

`PaperPipeline` (`src/pipeline/paper_pipeline.py`) runs four services in order: `ArxivService`, `PdfService` (`markitdown`), `LLMService`, `AudioService`. LLM and TTS go through `LLMProvider` / `TTSProvider` abstract classes (only OpenAI implementations exist). To add a provider: subclass in `src/services/llm_providers.py` or `tts_providers.py`, implement `generate()` / `generate_audio()`, and wire it in `backend/app/state.py`.

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
- Deploy: production changes only when the owner presses the **Deploy** workflow (main only, builds the chosen SHA's images if missing, rollback = an older SHA; see `deployment/github.md`). Every run waits in GitHub for the owner's approval (`production` requires the owner as reviewer). `scripts/ship.sh` is the laptop fallback and refuses a dirty tree on purpose. The deploy scripts have offline tests in `tests/deploy_scripts/` (a fake `az`). First request after idle is slow, and the shared serverless SQL DB can return transient 500s after a pause. Both explained in `deployment/local.md` and `deployment/operations.md`.
