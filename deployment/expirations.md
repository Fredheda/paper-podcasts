# Expirations & Renewals

Things in this deployment that expire on a clock, when, and how to renew
them. **Put the dated items in your calendar** — nothing here
auto-notifies you.

## Has a hard expiry — action required

| Item | Expires | Impact if it lapses | How to renew |
|------|---------|---------------------|--------------|
| **Easy Auth client secret** (Entra app `podcasts-easyauth`) | 2 years from setup — check with the command below | Login breaks for everyone; data/backend unaffected, only sign-in. | Re-run `./scripts/setup-easyauth.sh` — resets the secret, pushes it, restarts the frontend revision. |
| **`CLAUDE_CODE_OAUTH_TOKEN`** (GitHub repo secret used by `.github/workflows/claude-review.yml`) | About 2027-10-24 | The AI PR review stops posting comments. Nothing else is affected. | Run `claude setup-token`, then `gh secret set CLAUDE_CODE_OAUTH_TOKEN`. If subscription auth is refused, switch the action input to `anthropic_api_key`. |

Verify the current secret expiry any time:
```bash
az ad app credential list \
  --id "$(az ad app list --display-name podcasts-easyauth --query '[0].appId' -o tsv)" \
  --query "[].{start:startDateTime, end:endDateTime, keyId:keyId}" -o table
```

## No expiry — nothing to do

| Item | Why it never expires |
|------|----------------------|
| **ACR image pulls / Blob & SQL access** | User-assigned managed identity (`id-podcasts-acrpull`) — Azure rotates its tokens automatically. |
| **Image builds** | Authenticated by your live `az login` session, not a stored key. |
| **TLS certificates** (`*.azurecontainerapps.io` and `podcasts.frederikheda.com`) | Azure-managed and auto-renewed, as long as the `podcasts` CNAME keeps pointing directly at `ca-podcasts-web`'s FQDN. |

## Not time-based, but rotate if compromised

| Item | Notes |
|------|-------|
| **OpenAI API key** | Lives only as the `openai-api-key` Container Apps secret. Rotate via `./infra/deploy.sh` (prompts for/sources it) or `az containerapp secret set`. |
| **Entra B2B guest access** | Revoke anyone: Entra portal → Enterprise applications → `podcasts-easyauth` → Users and groups → remove. |

## Recurring (not an expiry, but a monthly clock)

Shares `acrchatbotfredheda` (ACR) and the `rg-chatbot` budget with
`copilot-kit-exp` and `Portfolio` — no separate line item for this project.

---

_Last reviewed: see git blame on this file._
