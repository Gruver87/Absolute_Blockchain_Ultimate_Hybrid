# Release notes — v1.3.180

## Summary

**Industrial GET_BLOCKS future-height honesty (no simplifications):**

1. **GET_BLOCKS future refuse** — inbound ranges with `from_height > local tip` get an empty `MSG_BLOCKS` reply (`get_blocks_future_height`).
2. Soft bandwidth/DoS honesty — no empty-loop fetch over fantasy future heights.
3. Sequel to v1.3.178 (GET_MEMPOOL tip-align) serve-side gates.

## Changes

- `network/p2p_node.py` — `_get_blocks_future_refuse_reason` in `_handle_get_blocks`
- Config: `p2p_get_blocks_future_refuse` / `P2P_GET_BLOCKS_FUTURE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.180-industrial`

## Honesty

- Soft future-height serve gate — **not** tip proof, not Long-Range, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13180_get_blocks_future_refuse.py -q
```
