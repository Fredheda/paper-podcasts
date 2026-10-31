# Deployment

Paper Podcasts runs on Azure Container Apps. This page gives the mental model and tells you what to run for each kind of change.

## The mental model

Production is two container images running as two Azure Container Apps, in resource group `rg-chatbot` and environment `cae-podcasts` (westeurope).

| App | Image | Ingress | Role |
|-----|-------|---------|------|
| `ca-podcasts-agent` | `podcasts-agent` | internal only | FastAPI backend and pipeline, port 8000 |
| `ca-podcasts-web` | `podcasts-web` | external, behind login | React/Vite SPA served by an Express `server.js`, port 3000 |

Images live in ACR (`acrchatbotfredheda.azurecr.io`), tagged with the git commit SHA. There is no CI deploy: images are built from a laptop with `az acr build` and no stored registry credentials. The web app is locked behind Entra Easy Auth. Both apps scale to zero when idle.

## What to run, by what changed

| What changed | Run |
|---|---|
| Code in `src/`, `backend/` or `frontend/` | `./scripts/ship.sh` (see [local.md](local.md)) |
| Infrastructure (`infra/main.bicep`), secrets or the OpenAI key | `./infra/deploy.sh [tag]` (see [infra.md](infra.md)) |
| A new user needs access | `./scripts/approve-user.sh <email>` (see [operations.md](operations.md)) |
| Easy Auth secret near expiry | `./scripts/setup-easyauth.sh` (see [expirations.md](expirations.md)) |

## Files

- [local.md](local.md): shipping a code change from your laptop.
- [infra.md](infra.md): what the infrastructure is and how it is provisioned.
- [operations.md](operations.md): approving users, logs, verifying production, idle behavior and known gotchas.
- [expirations.md](expirations.md): things that expire on a clock and how to renew them.

For local development and running the checks, see [docs/development.md](../docs/development.md).
