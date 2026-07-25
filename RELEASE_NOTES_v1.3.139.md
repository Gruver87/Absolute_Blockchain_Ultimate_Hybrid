# Release notes — v1.3.139

## Summary

**Industrial sync honesty (no simplifications):**

1. **Catch-up requires `peer.head`** — when `peer.height > local` but `peer.head` is empty (e.g. after soft height-cap cleared fantasy head), catch-up/`_schedule_sync` refuse. Stops height-only get_blocks DoS windows.
2. **Config** — `p2p_catch_up_require_head` / `P2P_CATCH_UP_REQUIRE_HEAD` (default true).

## Changes

- `_catch_up_ahead_refuse_reason` in `_schedule_sync` + `_sync_with_peer`
- Metrics: `native_catch_up_require_head`, `catch_up_no_head_refuse_total`
- `node_version`: `1.3.139-industrial`

## Honesty

- Soft scheduling gate — **not** tip existence proof, not merkle root-belongs-to-head, not fork-choice finality, not libp2p, not ceremony pin / public mainnet

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13139_p2p_catch_up_require_head.py -q
```
