# Release v1.2.16 — prod mesh startup fix

**Date:** 2026-07-06

## Summary

Fix prod 3-node Docker mesh: followers no longer crash-loop on startup; restarts with preserved RocksDB volumes work without manual `-NoCloneDb`.

## Changes

### Fixed

- **`main.py`**: synced prod followers (`follower_genesis_sync`, height > 1, no mining) may run watch-only — `require_wallet_file` no longer requires loading `private_key` when wallet.json is present
- **`docker_prod_3node.ps1` / `.sh`**: `-KeepVolumes` auto-skips DB seed (preserved chain data)
- **`docker_prod_3node.ps1`**: no-seed path starts all 3 nodes together (faster restart)
- **`docker_prod_3node.ps1`**: node2/node3 wait on `/health/ready` (5 min), dump logs on failure

## Test plan

- [x] Fresh mesh: `.\scripts\docker_prod_3node.ps1` — 3 nodes healthy, verify_p2p OK
- [x] Restart: `.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes` — no seed failure at height > 1
- [ ] CI Blockchain Tests + Docker prod image on master after tag push

## Upgrade

```powershell
git pull
.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes
```

Fresh chain (wipe volumes):

```powershell
.\scripts\docker_prod_3node.ps1
```
