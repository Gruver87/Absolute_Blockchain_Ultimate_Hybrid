# Release notes — v1.3.175

## Summary

**Industrial catch-up contiguous parent ownership honesty (no simplifications):**

1. **Catch-up contiguous parent bind** — during `get_blocks` import, a block at tip+1 must cite local tip as `parent_hash` (`catch_up_contiguous_parent_mismatch`).
2. Sequel to v1.3.157 (peer.head +1 probe parent) + v1.3.160/165 (NEW_BLOCK/reconcile contiguous) — every catch-up body, not only peer.head.

## Changes

- `network/p2p_node.py` — `_catch_up_contiguous_parent_refuse_reason` in catch-up import loop
- Config: `p2p_catch_up_contiguous_parent_bind` / `P2P_CATCH_UP_CONTIGUOUS_PARENT_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.175-industrial`

## Honesty

- Soft contiguous parent bind at catch-up import — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13175_catch_up_contiguous_parent_bind.py -q
```
