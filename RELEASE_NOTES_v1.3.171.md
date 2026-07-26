# Release notes — v1.3.171

## Summary

**Industrial reconcile tip-sibling ownership honesty (no simplifications):**

1. **Reconcile same-height parent bind** — when fetched head height equals local tip, `parent_hash` must match expected tip-height parent (`reconcile_same_height_parent_mismatch`).
2. Sequel to v1.3.165 (reconcile contiguous +1) + v1.3.168/169/170 (fork/GHOST/NEW_BLOCK same-height parent).

## Changes

- `network/p2p_node.py` — `_reconcile_same_height_parent_refuse_reason` in `_reconcile_to_head_hash`
- Config: `p2p_reconcile_same_height_parent_bind` / `P2P_RECONCILE_SAME_HEIGHT_PARENT_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.171-industrial`

## Honesty

- Soft tip-sibling parent bind at reorg choke point — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13171_reconcile_same_height_parent_bind.py -q
```
