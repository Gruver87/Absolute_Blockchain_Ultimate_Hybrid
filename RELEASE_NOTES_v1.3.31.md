# Release notes — v1.3.31

**Date:** 2026-07-21  
**Theme:** Oracle quorum, sync finally, peer fork, bridge ops, MEV/AI/will honesty

## Honesty / fail-closed

- Oracle: signature required when secret set; unique reporters for quorum; freshness gate
- Consensus Casper/Beacon `healthy` requires zero ingest failures
- SyncEngine `fast_sync` clears `is_syncing` in `finally`; exposes `sync_fail` / last error
- P2P topology: `transport_healthy` vs `chain_compatible` (same-height fork)
- RustBridge ops counters (decode/timeout/bin/cmd) via `get_ops_errors`
- MEV: `heuristic_signals` / `model_estimate` labels; AI: no fake confidence; will persist refund

## Config

- `node_version`: `1.3.31-industrial`

## Tests / gates

- `tests/unit/test_v1331_honesty.py`
- Industrial gate needles for the above paths

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch · wiring BlockBuilder into forge
