# Release notes — v1.3.170

## Summary

**Industrial NEW_BLOCK tip-sibling ownership honesty (no simplifications):**

1. **NEW_BLOCK same-height parent bind** — when announce height equals local tip, `parent_hash` must match expected tip-height parent (`new_block_same_height_parent_mismatch`), before tip mutate / LMD feed.
2. Sequel to v1.3.160 (+1 contiguous parent) + v1.3.168/169 (fork/GHOST same-height parent).

## Changes

- `network/p2p_node.py` — `_new_block_same_height_parent_refuse_reason` in `_handle_new_block`
- Config: `p2p_new_block_same_height_parent_bind` / `P2P_NEW_BLOCK_SAME_HEIGHT_PARENT_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.170-industrial`

## Honesty

- Soft tip-sibling parent bind — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13170_new_block_same_height_parent_bind.py -q
```
