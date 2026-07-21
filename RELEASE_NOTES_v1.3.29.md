# Release notes — v1.3.29

**Date:** 2026-07-21  
**Theme:** Topology/prod, eth filters, aux migrate, SQLite feature decode, metrics/WS, backup tip

## Honesty / fail-closed

- Prod/staging `topology_healthy` requires peers (mesh_min / ≥1)
- `eth_getFilterChanges` / `Logs` / `uninstallFilter` raise when filters unbound
- Hybrid aux→Rocks migrate skips corrupt JSON and does not mark migrated
- SQLite plasma/wills/WASM/AI/MEV/NFT/meta use counted decode helpers
- Metrics: `abs_sqlite_json_decode_failures`, `abs_aux_*`, `abs_ws_send_failures_total`
- Alerts: `AbsoluteSqliteJsonDecodeFailures`, `AbsoluteWSSendFailBurst`
- WS clears `_running` on bind/runtime failure; `/status` exposes WS subsystem
- `read_chain_tip` raises on missing/corrupt storage (no fake tip 0)

## Config

- `node_version`: `1.3.29-industrial`

## Tests / gates

- `tests/unit/test_v1329_honesty.py`
- Industrial gate needles for the above paths

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch · wiring BlockBuilder into forge
