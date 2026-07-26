# Release notes — v1.3.153

## Summary

**Industrial NEW_BLOCK ownership honesty (no simplifications):**

1. **Announce head↔height local bind** — if `new_block` hash is already known locally, claimed height must match that header (`new_block_head_height_mismatch`).
2. Refuses tip inflation / sync schedule on mismatched gossip (soft ownership).
3. Config: `p2p_new_block_head_height_bind` / `P2P_NEW_BLOCK_HEAD_HEIGHT_BIND` (default on).

## Changes

- `network/p2p_node.py` — `_new_block_head_height_refuse_reason` before tip mutate
- Config / metrics / security status
- `node_version`: `1.3.153-industrial`

## Honesty

- Soft wire bind — **not** tip existence proof, not merkle tip proof, not Long-Range / libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
.\scripts\check_all.ps1 -Mode Standard
python -m pytest tests/unit/test_v13153_new_block_head_height_bind.py -q
```
