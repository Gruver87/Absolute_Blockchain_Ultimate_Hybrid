# Release notes — v1.3.150

## Summary

**Standard pytest honesty needle fix (no protocol change):**

1. **`new_tx` rate** — `test_p2p_rate_limit_exempts_sync_types` matches v1.3.143 (MSG_NEW_TX on primary budget, not exempt).
2. **Rocks point-gets** — `test_rocks_point_gets_use_loads_helper` accepts dual-read helpers (`_loads_tx_blob_or_none` / `_loads_block_blob_or_none`) from v1.3.148/149.

## Changes

- `tests/unit/test_p2p_industrial.py`
- `tests/unit/test_supply_broadcast_honesty.py`
- `node_version`: `1.3.150-industrial`

## Honesty

- Test/needle alignment only — **not** tip proof / Long-Range / libp2p / public mainnet / full Rocks rewrite

## Verify

```text
.\scripts\check_all.ps1 -Mode Standard
python -m pytest tests/ -q --tb=line
```
