# Release notes — v1.3.181

## Summary

**Industrial GET_BLOCK future-height honesty (no simplifications):**

1. **GET_BLOCK future refuse** — inbound single fetches with `height > local tip` get a null `MSG_BLOCK` reply (`get_block_future_height`).
2. Soft bandwidth/DoS honesty — no DB lookup for fantasy future heights.
3. Sequel to v1.3.180 (GET_BLOCKS future-height).

## Changes

- `network/p2p_node.py` — `_get_block_future_refuse_reason` on `MSG_GET_BLOCK`
- Config: `p2p_get_block_future_refuse` / `P2P_GET_BLOCK_FUTURE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.181-industrial`

## Honesty

- Soft future-height serve gate — **not** tip proof, not Long-Range, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13181_get_block_future_refuse.py -q
```
