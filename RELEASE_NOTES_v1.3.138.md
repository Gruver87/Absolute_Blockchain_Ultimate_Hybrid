# Release notes — v1.3.138

## Summary

**Industrial honesty (no simplifications / no fake ceremony pin):**

1. **Solicit-only `state_root_response`** — unsolicited `MSG_STATE_ROOT_RESPONSE` is struck and never mutates `_state_consistent` (mirrors mempool/blocks). Only active state_root waiters fulfill.
2. **Ceremony status in `check_all`** — `scripts/ceremony_status.py` reports pin/dir readiness honestly (exit 0 by default). Never invents `GENESIS_CEREMONY_HASH`. Wired into `.\scripts\check_all.ps1`.

## Changes

- Waiter + free-path solicit-only for state_root_response
- Metrics: `native_state_root_solicit_only`, `unsolicited_state_root_rejects_total`
- `scripts/ceremony_status.py` + `check_all.ps1` step `ceremony_status`
- `node_version`: `1.3.138-industrial`

## Honesty

- Solicit-only gate is **not** tip proof / root-belongs-to-head merkle proof
- Ceremony status green ≠ public mainnet / completed external audit — pin remains operator-owned

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13138_state_root_solicit_and_ceremony_status.py -q
```
