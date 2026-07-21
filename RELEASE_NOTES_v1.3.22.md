# Release notes — v1.3.22

**Date:** 2026-07-21  
**Theme:** Rocks decode counter, topology/reconcile, SyncEngine prod, eth_mining mesh

## Honesty / fail-closed

- Rocks list paths (proposer_audit / bridge_locks / state_root mismatches): bump `json_decode_failures` + warn
- Prometheus: `abs_rocksdb_json_decode_failures` + alert `AbsoluteRocksJsonDecodeFailures`
- Production boot hard-fails when SyncEngine unavailable
- `topology_healthy` requires `state_consistent` when peers are present
- `reconcile_peers` without SyncEngine clears `_state_consistent`
- `eth_mining`: mesh_min_peers / state_consistent gate (config-on ≠ forging)

## Config

- `node_version`: `1.3.22-industrial`

## Tests / gates

- `tests/unit/test_rocks_topology_honesty.py`
- Industrial gate needles for rocks decode / topology / SyncEngine prod / eth_mining

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch
