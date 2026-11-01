# Deploying from GitHub (the Deploy button)

Production changes only when you press **Deploy** on GitHub. Merging to `main` builds and deploys nothing, and CI never builds.

## Deploy

Actions tab, then **Deploy**, then Run workflow on `main`, or:

```bash
gh workflow run deploy.yml --ref main              # the head of main
gh workflow run deploy.yml --ref main -f sha=<full 40-character commit SHA>
gh run watch
```

The run stops at `waiting` until the owner approves it: Actions, the run, **Review deployments**, approve. The owner is the only required reviewer of `production`, and admins cannot bypass it. An agent never approves a waiting deployment. `gh run watch` keeps polling while the run waits; run it again after the approval.

The workflow (`.github/workflows/deploy.yml`, `production` environment, `main` only):

1. Checks the SHA is a full lowercase commit SHA on `main`, before any Azure login.
2. Logs in as the **build** identity and runs `scripts/build-push.sh <sha>`. It builds `podcasts-agent` and `podcasts-web` from `git archive <sha>` and skips any image that already exists, so a repeat deploy or a rollback to an already-built commit builds nothing.
3. Logs in as the **deploy** identity and runs `scripts/redeploy.sh <sha>`. It refuses unless both images exist, rolls `ca-podcasts-agent` and `ca-podcasts-web`, locks the tags now running and unlocks the ones replaced (`latest` is never touched).
4. `scripts/wait-healthy.sh` waits until both new revisions are `Provisioned`; the run summary shows the SHA, commit subject and revisions.

**Rollback** is the same button with an older SHA. **Infrastructure** (`infra/main.bicep`, secrets) is not part of the button: run `./infra/deploy.sh <deployed-sha>` from a laptop, passing the SHA that is deployed (its tag default is local `HEAD`, which could roll the apps to a different commit).

## One-time setup (already done by `scripts/setup-github-deploy.sh`)

The script is idempotent. It creates the managed identities `id-podcasts-gh-build` (`AcrPush`, `Container Registry Tasks Contributor`) and `id-podcasts-gh-deploy` (`AcrPush`, `Container Apps Contributor` on each app, `Managed Identity Operator` on `id-podcasts-acrpull`), a federated credential on each that trusts only jobs in this repo's `production` environment, restricts that environment to `main`, makes the repo owner its required reviewer, and stores `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_BUILD_CLIENT_ID` and `AZURE_DEPLOY_CLIENT_ID` as repo **secrets** (the repo is public, and secrets are masked in run logs). No credential is stored anywhere.

## Registry clean-up

`scripts/setup-acr-purge.sh` locks the SHA each app runs and prints a dry run of what the weekly purge would delete (full-SHA tags of `podcasts-agent` and `podcasts-web` only, older than 30 days, newest 10 kept, never `latest`, never locked tags). `./scripts/setup-acr-purge.sh --create` creates the task `purge-podcasts-images` (Sundays 03:00 UTC) after you have read the dry run.

## Known limits

- The registry is in legacy permission mode, so pushes cannot be scoped per repository: the deploy identity's `AcrPush` also allows pushing, and the build identity can push registry-wide.
- `redeploy.sh` updates the apps one at a time, so a failure between them can leave mixed versions until the button is pressed again with the right SHA.
- The first deploy of a commit runs two ACR builds, which are billed (the ACR Tasks price is not on Microsoft Learn: check Cost Management).
- Turn on "automatically delete head branches" for the repo.

Laptop fallback: [local.md](local.md).
