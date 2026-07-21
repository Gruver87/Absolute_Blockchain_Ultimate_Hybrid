# Release notes — v1.3.19

**Date:** 2026-07-21  
**Theme:** Sync incomplete honesty, CORS allowlist miss, repair success, receipt fail-closed

## Sync / P2P

- Catch-up sync: log **Sync incomplete** when tip &lt; peer height; do **not** claim complete or set state_root baseline until `reached_target`
- Always still run `sync_engine.sync_state()` after catch-up

## API honesty

- CORS: allowlist miss → empty origin (**never** echo first allowlist entry)
- `POST /chain/consistency/repair`: `success` requires tip repair **and** harness healthy **and** wire/sync consistent

## Storage

- SQLite `_normalize_tx_status`: missing/unknown status → **0** (fail-closed); omit key on insert → success `1`

## Gates / verify

- Industrial gate needles for sync incomplete, CORS, repair success formula, receipt normalize

## Explicit non-goals (unchanged)

- External audit complete · live L1 contracts · public mainnet launch
