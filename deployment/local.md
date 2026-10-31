# Shipping a code change from your laptop

```bash
./scripts/ship.sh
```

The script builds and pushes both images for the current commit (`scripts/build-push.sh`, which uses `az acr build`), then rolls both container apps to them (`scripts/redeploy.sh`). It needs `az login` and a clean working tree. It refuses to run on a dirty tree so that the image tag always matches the deployed commit.

For infrastructure changes (`infra/main.bicep`, secrets), use `./infra/deploy.sh` instead. See [infra.md](infra.md).

After shipping, verify the result as described in [operations.md](operations.md).

## Known gotcha: re-shipping under an unchanged image tag

`./scripts/build-push.sh` and `az acr build` build the working tree, not the committed SHA. If you rebuild and push without committing first, the image tag string stays the same even though the pushed image content changed. `az containerapp update --image <same-tag>` can then silently keep serving the old revision, because Container Apps does not always detect that an unchanged tag now points at a different digest.

`./scripts/ship.sh` avoids this by refusing a dirty tree, so a new commit, and therefore a new tag, always exists before shipping. If you ever need to force a fresh revision manually:

```bash
az containerapp update -n <app> -g rg-chatbot --image <image> --revision-suffix <unique>
```
