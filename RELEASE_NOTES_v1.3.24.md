# Release notes — v1.3.24

**Date:** 2026-07-21  
**Theme:** Core engines prod hard-fail, status wire probe, IMS canonical, Rocks meta/tx

## Honesty / fail-closed

- Prod boot hard-fails without StateEngine / FinalityEngine / ImmutableStateManager
- `/health/ready` (prod): checks `state_engine`, `finality_engine`, `immutable_state`
- `/status`: `degraded` when peers + never-probed / probe-fail wire
- `/state/abs-balance` and `/state/total-supply`: DB-only → `canonical=false`, `ims_available=false`
- Rocks `get_meta` + address/block/recent TX lists + reorg purge bump `json_decode_failures`
- Metrics: `abs_state_engine_available` / `abs_finality_engine_available` / `abs_ims_available` + alert

## Config

- `node_version`: `1.3.24-industrial`

## Tests / gates

- `tests/unit/test_core_engines_honesty.py`
- Industrial gate needles for core engines / status wire / IMS canonical / rocks floor≥15

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch
