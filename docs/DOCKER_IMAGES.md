# Docker images (honest ops guide)

**Updated:** 2026-07-05

This project ships two primary node images:

| Dockerfile | Use case | Local tag (default) |
|------------|----------|---------------------|
| `Dockerfile.prod` | Mainnet-v1 prep / prod mesh (RocksDB, native required) | `abs-blockchain-prod:local` |
| `Dockerfile.devnet-rust` | Devnet 2/3/5-node meshes (chain 77777) | compose project image |

## BuildKit (recommended)

```powershell
$env:DOCKER_BUILDKIT = "1"
$env:COMPOSE_DOCKER_CLI_BUILD = "1"
docker compose -f docker-compose.prod.3node.yml build
```

Both prod and devnet Dockerfiles use **Cargo fetch cache layers** and **BuildKit mount caches** so rebuilds after Python-only changes reuse Rust artifacts.

## GHCR prod image (CI-published)

| Item | Value |
|------|-------|
| Registry | `ghcr.io` |
| Image | `ghcr.io/gruver87/abs-blockchain-node` |
| Tags | `latest` (master), git SHA, semver on `v*` tags |
| Workflow | `.github/workflows/docker-prod-image.yml` |

**Truth:** the image exists on GHCR **only after** the workflow succeeds on `master`. It is not pre-published. Check Actions tab first.

### Pull and run prod mesh without local build

```powershell
.\scripts\docker_prod_3node.ps1 -PullLatest -KeepVolumes -NoCloneDb
```

Or set in `.env`:

```
ABS_PROD_IMAGE=ghcr.io/gruver87/abs-blockchain-node:latest
```

Then:

```powershell
.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes -NoCloneDb
```

Public repo → public package → **no login required** for pull.

## Local fast paths

| Goal | Command |
|------|---------|
| First prod mesh build | `.\scripts\docker_prod_3node.ps1` |
| Restart, keep RocksDB | `.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes -NoCloneDb` |
| Quick restore wrapper | `.\scripts\quick_restore.ps1 -KeepData` |
| Full wipe + rebuild | `docker compose -p abs-prod-mesh3 -f docker-compose.prod.3node.yml down -v` then mesh script |

## What is NOT included

- No official mainnet deployment image with real validator keys baked in
- No GHCR devnet image yet (devnet still builds `Dockerfile.devnet-rust` via compose)
- No non-root container user (RocksDB volume permissions on Windows need separate testing)

See also: [README.md](../README.md) · [docs/K8S_DEPLOY.md](K8S_DEPLOY.md)
