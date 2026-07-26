# Release notes — v1.3.176

## Summary

**Industrial catch-up height continuity honesty (no simplifications):**

1. **Catch-up height continuity bind** — during `get_blocks` import, body height must equal the expected sync cursor (`catch_up_height_continuity_mismatch`).
2. Soft refuse-before-mutate — out-of-order / skip-ahead bodies must not force expensive import/reorg under DoS.
3. Sequel to v1.3.175 (contiguous parent) + v1.3.172 (tip-head).

## Changes

- `network/p2p_node.py` — `_catch_up_height_continuity_refuse_reason` before contiguous/tip binds in import loop
- Config: `p2p_catch_up_height_continuity_bind` / `P2P_CATCH_UP_HEIGHT_CONTINUITY_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.176-industrial`

## Honesty

- Soft sync-cursor bind — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13176_catch_up_height_continuity_bind.py -q
```
