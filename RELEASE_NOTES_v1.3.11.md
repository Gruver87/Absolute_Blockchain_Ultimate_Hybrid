# Release notes — v1.3.11

**Date:** 2026-07-21  
**Theme:** Sync consistency metrics + loop/import honesty + deploy freezes

## Observability

- Prometheus: `abs_state_consistent`, `abs_sync_wire_probe_ok`, `abs_sync_wire_probe_probed`
- Alerts: `AbsoluteStateInconsistent`, `AbsoluteSyncWireProbeFail`
- Grafana panels for state consistent + wire probe
- Rocks tuning snapshot: warn on failure + `source=` label (`live` / `config_fallback` / `snapshot_fail`)

## P2P / sync honesty

- `import_block` exceptions → warn + `ops_errors.import_block_fail`
- `_sync_with_peer_safe` → `sync_fail`
- `_discovery_loop` / `_bootstrap_retry_loop` try/except + fail counters
- SyncEngine: unknown wire probe is fail-closed (`wire_probe_ok=false`, `wire_probe_probed=false`)

## Status / gates

- `/status` p2p security includes `ops_errors` + `attestation_local_fail` (primary + fallback)
- Compose freeze extends to `BRIDGE_ENABLED` / `REDIS_*` (default from `${VAR:-…}`)
- `k8s_prod_gate`: `bridge_enabled=false` + ConfigMap `BRIDGE_ENABLED: "false"`

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
