# Shipping a code change from your laptop (fallback)

The normal path is the **Deploy** button on GitHub: see [github.md](github.md). Use this when GitHub is unavailable.

```bash
./scripts/ship.sh
```

The script builds and pushes both images for the current commit (`scripts/build-push.sh`, which uses `az acr build` and skips images that already exist), then rolls both container apps to them (`scripts/redeploy.sh`, which checks every image first and locks the deployed tags). It needs `az login` and a clean working tree. It refuses to run on a dirty tree so that what is deployed is always a commit you can name.

For infrastructure changes (`infra/main.bicep`, secrets), use `./infra/deploy.sh <deployed-sha>` instead. See [infra.md](infra.md).

After shipping, verify the result as described in [operations.md](operations.md).

If a rollout ever keeps serving an old revision under an unchanged tag, force a fresh one:

```bash
az containerapp update -n <app> -g rg-chatbot --image <image> --revision-suffix <unique>
```
