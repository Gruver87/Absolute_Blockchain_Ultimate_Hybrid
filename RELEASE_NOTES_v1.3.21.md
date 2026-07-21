# Release notes — v1.3.21

**Date:** 2026-07-21  
**Theme:** sync_state / mesh mining / bridge-L1 / ready peer_count honesty

## Honesty / fail-closed

- `sync_state` solo/no peers: clear `_state_consistent`, return `False` (never keep stale mesh-green)
- `sync_state` with peers: require ≥1 same-height peer root match before painting True
- `mesh_ready_for_mining`: STATUS height alignment requires `state_consistent`; default False
- `/status` `bridge_relayer_live`: rust bridge smoke ok (not `bridge_enabled` alone)
- `_rust_bridge_health` / L1 unconfigured: `ok=False` (no greenwash)
- `/health/ready` (prod): `peer_count()` probe failure fail-closes (`peer_count_probe` + consistency)

## Config

- `node_version`: `1.3.21-industrial`

## Tests / gates

- `tests/unit/test_sync_mesh_bridge_honesty.py`
- Soak includes cors/receipt + sync/mesh honesty + mesh_mining tests
- Industrial gate needles for solo/same-height/mesh/bridge/L1/ready

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch
