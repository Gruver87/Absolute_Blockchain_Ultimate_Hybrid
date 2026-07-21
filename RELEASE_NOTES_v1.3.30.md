# Release notes — v1.3.30

**Date:** 2026-07-21  
**Theme:** Ready/WS, feature init errors, bridge proof, L2 missing, storage, consensus healthy

## Honesty / fail-closed

- `/health/ready` (prod): `websocket_running` + feature init failure checks
- Optional module init failures tracked (`feature_init_errors`); `/status` degrades
- Bridge `proof_ok` requires ETH RPC; rust mode requires smoke health
- Lightning/Plasma/WASM unbound → `*_missing`; `/network/stats` → `p2p_missing`
- `eth_getStorageAt` raises on corrupt account storage (counted decode)
- Consensus adapter: ingest fail counters + `healthy` flag

## Config

- `node_version`: `1.3.30-industrial`

## Tests / gates

- `tests/unit/test_v1330_honesty.py`
- Industrial gate needles for the above paths

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch · wiring BlockBuilder into forge
