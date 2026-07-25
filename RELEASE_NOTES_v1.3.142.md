# Release notes — v1.3.142

## Summary

**Standard-gate fix (no simplifications):**

1. **Stale honesty needle** — `test_shared_sync_engine_and_unsolicited_state_root_honesty` still required the pre-v1.3.138 log string `Unsolicited state_root match`. Solicit-only strikes unsolicited `MSG_STATE_ROOT_RESPONSE` instead; the test now asserts that path.
2. Unblocks `check_all -Mode Standard` / full pytest (1499+).

## Changes

- `tests/unit/test_silent_except_honesty.py` — align with solicit-only state_root
- `node_version`: `1.3.142-industrial`

## Honesty

- Test/contract fix only — **not** tip proof, libp2p, ceremony pin, or public mainnet

## Verify

```text
.\scripts\check_all.ps1
.\scripts\check_all.ps1 -Mode Standard
python -m pytest tests/unit/test_silent_except_honesty.py::test_shared_sync_engine_and_unsolicited_state_root_honesty -q
```
