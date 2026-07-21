# Release notes — v1.3.25

**Date:** 2026-07-21  
**Theme:** supply canonical, Rocks point-gets, broadcast_fail, core_real engines

## Honesty / fail-closed

- `/state/supply`: DB-only never `canonical=true`; prefer IMS; expose `ims_available`
- Rocks point-gets (`get_block` / `get_transaction` / `get_tx_receipt` / account): `_loads_json_or_none` + decode counter
- P2P block/tx/attestation broadcast: inspect gather results → `ops_errors.broadcast_fail`
- `core_real`: engine flags; `finality_quorum_live=false` (local attestations split out)
- `/finality/*` and `/state/engine`: `error=*_missing` when unbound
- Prod: block signing failure hard-fails (no unsigned forge)

## Config

- `node_version`: `1.3.25-industrial`

## Tests / gates

- `tests/unit/test_supply_broadcast_honesty.py`
- Industrial gate needles for supply / point-gets / broadcast_fail / core_real / sign hard-fail

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch
