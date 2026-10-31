# Operations

## Approve a user

```bash
./scripts/approve-user.sh <email>
```

To revoke access, open the Entra portal, go to Enterprise applications, then `podcasts-easyauth`, then Users and groups, and remove the user.

## Verify in production

Open the custom domain, or look up the default URL (both are registered Easy Auth redirect URIs):

```bash
az containerapp show -n ca-podcasts-web -g rg-chatbot --query properties.configuration.ingress.fqdn -o tsv
```

## Logs

```bash
az containerapp logs show -n <app> -g rg-chatbot --follow
```

## Scale to zero and the three idle clocks

Both container apps scale to zero after the platform-default 5-minute cooldown. The first request after idle takes about 15 to 40 seconds.

There are three independent idle clocks, not one:

1. The container apps' own 5-minute cooldown.
2. `PlaygroundDB`, a serverless Azure SQL database shared with `Portfolio`. It auto-pauses after 60 minutes (`autoPauseDelayInMinutes: 60`), independently of the container apps.
3. The frontend's polling (`POLL_INTERVAL_MS` and `IDLE_PAUSE_MS` in `frontend/src/App.tsx`). It pauses after 60 seconds with no active or queued job and resumes on tab focus or a search or enqueue. Without this, an open tab would poll forever and neither container app could finish its cooldown.

A replica that dies mid-processing loses only the LLM and text-to-speech spend of the stage in flight. Re-triggering the job resumes from the last durably saved stage.

## Known gotcha: transient 500s after a long idle period

If nothing has used the app for more than 60 minutes, `PlaygroundDB` pauses. The next request wakes it, but the resume can take up to about 45 seconds. During that window `/api/library` and `/api/jobs` can return a real 500 (`mssql_python.OperationalError`, "database not currently available" or a TCP timeout), even though nothing is broken.

`AzureSqlMetadataService._connect()` retries a few times with a short backoff to absorb the tail of this, but it does not fully hide a fresh pause within a single request. If you see this while testing after a long gap, it is almost certainly this and not a regression. Wait a few seconds and retry.

## Cost

This project shares the `acrchatbotfredheda` registry and the `rg-chatbot` budget with `copilot-kit-exp` and `Portfolio`. It has no separate line item.
