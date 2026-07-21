# Release notes — v1.3.26

**Date:** 2026-07-21  
**Theme:** remaining gather, Rocks mutate, attestation errors, BlockBuilder honesty

## Honesty / fail-closed

- P2P: cross-shard / shard-migration / validator_register gather → `_record_broadcast_results`
- Rocks: `slash_validator` / `confirm_bridge_lock` / `get_total_burned` via `_loads_json_or_none`
- `/consensus/attestations*`, `/sharding/pending`, `/consensus/committee`, `/finality/epoch`, `/slashing/status`: `error=*_missing`
- BlockBuilder log: constructed but not wired into forge (no false “enabled”)
- Alert: `AbsoluteP2PBroadcastFailBurst`

## Config

- `node_version`: `1.3.26-industrial`

## Tests / gates

- `tests/unit/test_gather_mutate_honesty.py`
- Industrial gate needles for remaining gather kinds / mutate loads / missing errors / alert

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch · wiring BlockBuilder into forge
