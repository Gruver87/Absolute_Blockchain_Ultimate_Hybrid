# Release notes — v1.3.15

**Date:** 2026-07-21  
**Theme:** Sync/RPC honesty + SQLite metrics engine label + compose freeze

## Sync / RPC

- Missing `get_state_root` → fail-closed (`state_consistent=False`)
- `eth_syncing` stays syncing when peers exist and tip is inconsistent / wire probe failed
- Admin `/chain/consistency/repair` sets `_state_consistent` only via `sync_state` (not harness alone)

## Storage / metrics

- SQLite `get_stats` / `get_chain_metrics` expose `engine: "sqlite"` + honest receipts/audit flags
- Prometheus `abs_db_engine`; Rocks tuning gauges only when engine is RocksDB (no SQLite `config_fallback`)

## Gates

- industrial_gate freezes `DB_ENGINE`↔`db_engine`, `JWT_ENFORCE_ADMIN`↔`jwt_enforce_admin`
- Needles for sync fail-closed, eth_syncing honesty, repair sync_state, metrics engine

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
