# Release notes — v1.3.28

**Date:** 2026-07-21  
**Theme:** Mining/status honesty, WS/P2P send fail-loud, API missing keys, clone/SQLite/amount

## Honesty / fail-closed

- `eth_mining`: prod/staging without P2P → false; bound P2P must be `_running`
- `/status`: degraded when peers present without SyncEngine; expose `subsystems`
- Unbound `/smart-account/*`, `/sync/peers`, `/contracts` → `*_missing` error keys
- WebSocket `_broadcast` increments `_send_failures`; legacy `MessageHandler._send` counts unbound/fail
- Rocks clone: checkpoint fail-closed when `RocksEngine` available (no silent copytree)
- SQLite `_loads_json_or_none` + `json_decode_failures` for blocks / prop / minivm / evm topics
- `runtime/amount.py`: `REQUIRE_NATIVE_CRYPTO` raises on native failure; otherwise warn once

## Config

- `node_version`: `1.3.28-industrial`

## Tests / gates

- `tests/unit/test_ws_status_clone_honesty.py`
- Industrial gate needles for the above paths

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch · wiring BlockBuilder into forge
