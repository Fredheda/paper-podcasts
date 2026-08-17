# Deployment & Change Workflow

How to make a change, test it locally, and ship it to Azure.

For *what* the infrastructure is and *why*, see the "Deployment (Azure
Container Apps)" section of [`CLAUDE.md`](./CLAUDE.md) and the full plan at
`docs/paper-podcasts/plans/2026-08-15-paper-podcasts-deployment.md` (workspace root). For
anything that expires on a clock, see [`EXPIRATIONS.md`](./EXPIRATIONS.md).

## The mental model

Production is **two container images** running as **two Azure Container
Apps**:

| App | Image | Ingress | Role |
|-----|-------|---------|------|
| `ca-podcasts-agent` | `podcasts-agent` | **internal only** | FastAPI backend + pipeline |
| `ca-podcasts-web` | `podcasts-web` | public (behind login) | React/Vite SPA + Express proxy |

Images live in ACR (`acrchatbotfredheda.azurecr.io`), tagged with the git
commit SHA. The frontend is locked behind Entra Easy Auth. Both apps scale to
zero when idle.

## Step 1 — Make your change

- Shared pipeline logic (download/extract/summarize/audio) → `src/`
- Backend API → `backend/app/`
- Frontend → `frontend/src/`

## Step 2 — Test locally

```bash
poetry run pytest -v      # offline, local storage backend
poetry run honcho start   # backend + frontend together, via the repo-root Procfile
```

Open http://localhost:5173 (note: `localhost`, not `127.0.0.1` — Vite's dev
config binds to the hostname specifically). `STORAGE_BACKEND` defaults to
`local` — no Azure credentials needed for any of the above. See
[`CLAUDE.md`](./CLAUDE.md)'s "Quick Start Commands" for the two-terminal
alternative if you want the servers separate.

## Step 3 — Ship it

```bash
./scripts/ship.sh
```

Refuses to run on a dirty working tree (the image tag must honestly match
the deployed commit). For infra changes (`infra/main.bicep`, secrets), use
`./infra/deploy.sh` instead.

## Step 4 — Verify in production

```
https://podcasts.frederikheda.com
```

The default Container Apps URL also works — both are registered Easy Auth
redirect URIs. Look it up any time:

```bash
az containerapp show -n ca-podcasts-web -g rg-chatbot --query properties.configuration.ingress.fqdn -o tsv
```

## Known gotcha: re-shipping under an unchanged image tag

`./scripts/build-push.sh`/`az acr build` builds the **working tree**, not
the committed SHA — if you rebuild+push without committing first, the image
tag string stays the same even though the pushed image content changed.
`az containerapp update --image <same-tag>` can then silently keep serving
the old revision, since Container Apps doesn't always detect that an
unchanged tag now points at a different digest. `./scripts/ship.sh` avoids
this by refusing a dirty tree (so a new commit — and thus a new tag — always
exists before shipping). If you ever do need to force a fresh revision
manually: `az containerapp update -n <app> -g rg-chatbot --image <image> --revision-suffix <unique>`.
