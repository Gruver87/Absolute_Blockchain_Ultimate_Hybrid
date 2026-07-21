# Release notes — v1.3.27

**Date:** 2026-07-21  
**Theme:** Rocks NFT/EVM/tx-prop decode, catch_up gather, IMS/sharding missing, get_meta

## Honesty / fail-closed

- Rocks: tx-prop / EVM / NFT decode helpers via `_loads_json_or_none`; nested corrupt fields bump counter
- Rocks `get_meta`: corrupt JSON → `default` (never garbage string); legacy plain-string meta (e.g. `schema_version`) preserved
- P2P `catch_up_sync` gather → `_record_broadcast_results(kind="catch_up_sync")`
- `/state/stats|/state/all|/state/balance`: `immutable_state_missing`; `/status` sharding + reshard: `sharding_missing`
- Alerts: `AbsoluteP2PPeerSyncFailBurst`, `AbsoluteP2PCatchUpLoopFailBurst`

## Config

- `node_version`: `1.3.27-industrial`

## Tests / gates

- `tests/unit/test_decode_catchup_honesty.py`
- Industrial gate needles for decode helpers / catch_up / IMS missing / sync alerts

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch · wiring BlockBuilder into forge
