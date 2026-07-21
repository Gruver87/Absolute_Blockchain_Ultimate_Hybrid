# Release notes — v1.3.13

**Date:** 2026-07-21  
**Theme:** Rocks/CORS/TLS overlay honesty + fail-closed state_consistent defaults

## Honesty

- `/status` + mining/sync: `_state_consistent` defaults **False** when missing (not green)
- Rocks `reorg_truncate_above` logs corrupt block JSON; `get_stats` surfaces property/tuning errors
- Mempool signature verify exceptions → warning (not silent False)
- Cross-shard gossip failures → warning; same-node migration logs explicit noop

## Deploy

- `docker-compose.prod.3node.p2ptls.yml`: `P2P_TLS_FAIL_CLOSED` + `P2P_TLS_BIND_IDENTITY` (parity with single-node)
- industrial_gate freezes both p2ptls overlays
- CORS RPC proxy honors `cors_origins`; prod refuses `*`; upstream errors → 502
- `.env.example`: `ENABLE_CORS_RPC_PROXY=false`, no `CORS_ORIGINS=*`

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
