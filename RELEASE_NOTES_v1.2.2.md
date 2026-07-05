# Release v1.2.2 — Docker GHCR + fast mesh ops

**Date:** 2026-07-05 · **API wave:** 61

## Summary

Production Docker workflow: faster rebuilds, optional GHCR pull, no mainnet launch claims.

## Changes

- **BuildKit cache** in `Dockerfile.prod` and `Dockerfile.devnet-rust`
- **`-SkipBuild` / `-KeepVolumes`** on prod 3-node mesh scripts
- **`scripts/quick_restore.ps1`** — fast restart with data
- **GHCR CI:** `ghcr.io/gruver87/abs-blockchain-node` via `.github/workflows/docker-prod-image.yml`
- **`-PullLatest`** — pull CI image instead of local build
- **`docs/DOCKER_IMAGES.md`** — honest ops guide
- Prometheus prod mesh targets `:18180–18182`

## Usage

```powershell
# Local build (first time)
.\scripts\docker_prod_3node.ps1

# Fast restart
.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes -NoCloneDb

# After CI publishes image on master
.\scripts\docker_prod_3node.ps1 -PullLatest -KeepVolumes -NoCloneDb
```

## Not included

- Public mainnet launch
- GHCR devnet image (devnet still uses compose build)
- Non-root container user
