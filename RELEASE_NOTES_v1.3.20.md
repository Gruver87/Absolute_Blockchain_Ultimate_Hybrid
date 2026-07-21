# Release notes — v1.3.20

**Date:** 2026-07-21  
**Theme:** Proxy CORS honesty, receipt omit→0, ready/sync fail-closed

## Honesty / fail-closed

- CORS: empty allowlist must not promote to `*`; miss never echoes first allowlist entry (REST + CORS RPC proxy)
- `/health/ready` (prod): with peers, requires `state_consistent`
- Sync status: SyncEngine missing with peers → `p2p_fallback` fail-closed (`SyncEngine missing`)
- Receipts: omitted/unknown tx status → `0x0` via `Database._normalize_tx_status`

## Config

- Default `cors_origins=[]` (not `*`)
- `node_version`: `1.3.20-industrial`

## Tests / gates

- `tests/unit/test_cors_receipt_ready_honesty.py`
- Industrial gate needles for CORS / ready / p2p_fallback / receipt normalize

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch
