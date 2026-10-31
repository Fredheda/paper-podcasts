# Infrastructure

Infrastructure is defined in `infra/main.bicep` and deployed with `infra/deploy.sh [tag]`. Use it to provision the environment for the first time and for any change to infrastructure, secrets or the OpenAI key.

## What exists

- Two consumption-plan container apps, `ca-podcasts-agent` and `ca-podcasts-web`, in `rg-chatbot` / `cae-podcasts` (westeurope).
- Images in ACR `acrchatbotfredheda.azurecr.io`, shared with `copilot-kit-exp` and `Portfolio`. Images are built with `scripts/build-push.sh` (`az acr build`), with no stored registry credentials.
- A user-assigned managed identity, `id-podcasts-acrpull`, with AcrPull and Storage Blob Data Contributor (the latter scoped to the `paper-podcasts` blob container). The apps use it to pull images and reach storage.
- The backend runs with `STORAGE_BACKEND=azure`. It reuses the storage account `fhstorageportfolio` and the `PlaygroundDB` database on the `fhdbplayground` SQL server, both shared with `Portfolio`.
- The OpenAI key lives only as the `openai-api-key` Container Apps secret.
- The default `*.azurecontainerapps.io` URL and the custom domain are both bound to `ca-podcasts-web`. The custom domain uses a free Azure-managed TLS certificate.
- The environment omits `appLogsConfiguration`, so there is no Log Analytics meter.
- Both apps set `minReplicas: 0`. `cooldownPeriod` is not set, so the platform default of 300 seconds applies.

## Sign-in (Easy Auth)

`ca-podcasts-web` is protected by Entra Easy Auth, using the Entra app `podcasts-easyauth` with assignment required. `scripts/setup-easyauth.sh` configures it. It registers redirect URIs for both the custom domain and the default FQDN, and it also resets the client secret (see [expirations.md](expirations.md)).

Only users assigned to the app can sign in. To grant access, see [operations.md](operations.md).

## Design

The full design is in the workspace-level spec `docs/paper-podcasts/specs/2026-08-15-paper-podcasts-deployment.md` and plan `docs/paper-podcasts/plans/2026-08-15-paper-podcasts-deployment.md`.
