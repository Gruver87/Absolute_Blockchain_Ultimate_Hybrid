# Release notes — v1.3.23

**Date:** 2026-07-21  
**Theme:** P2P bind fail-closed, ready wire probe, status degraded, peers mining gate

## Honesty / fail-closed

- P2P bind failure: `_running=False` and return (no green listener)
- `/health/ready` (prod): with peers requires wire_probe_probed/ok; `p2p_running` needs bound `_server`
- `/status`: `degraded` when peers + inconsistent tip (or P2P not running)
- Mining / `eth_mining`: peers present require `state_consistent` even when `mesh_min=0`
- Rocks scan/reorg paths bump `json_decode_failures` (latest blocks / accounts / validators / reorg)

## Config

- `node_version`: `1.3.23-industrial`

## Tests / gates

- `tests/unit/test_bind_ready_status_honesty.py`
- Industrial gate needles for bind / ready wire / status / peers mining / rocks floor≥10

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch
