# Release notes — v1.3.03

**Date:** 2026-07-21  
**Theme:** Observability + ceremony UX + deploy Rocks env

## Observability

- `GET /metrics` — `abs_p2p_shape_rejects_total`, per-reason `abs_p2p_shape_rejects`, handshake rejects, active bans
- `GET /status` P2P security summary includes `shape_rejects_total` / `shape_rejects`

## Ceremony gate UX

- `mainnet_readiness` / industrial gate auto-detect ceremony dir from:
  - `data/ceremony_deploy.json`
  - `data/ceremony_keys` (or `data/ceremony`) when manifest present
- Clearer warning when `GENESIS_CEREMONY_HASH` is set without a resolvable ceremony dir

## Deploy

- `docker-compose.prod.yml` / `prod.3node.yml` / `deploy/k8s/configmap.yaml`:
  - `ROCKSDB_BLOCK_CACHE_MB=256`
  - `ROCKSDB_WRITE_BUFFER_MB=64`
  - `ROCKSDB_COLUMN_FAMILIES=false`

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
