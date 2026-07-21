# Release notes — v1.3.18

**Date:** 2026-07-21
**Theme:** fast_sync honesty, Rocks TX-iter fail-loud, ready DB probe

## Sync

- `SyncEngine.fast_sync` success paths re-check via `sync_state()` (no blind `True`)
- Zero peers while `_last_wire_probe_ok` was True → reset to never-probed (`None`)

## Storage

- Rocks `_iter_transaction_rows`: corrupt JSON → warn + `json_decode_failures` (not silent skip)

## API

- `/health/ready`: live DB probe (`get_stats` / `get_height`); `db_probe_error` on failure

## Explicit non-goals

- Public mainnet / external audit complete
- Bridge L1 enablement
