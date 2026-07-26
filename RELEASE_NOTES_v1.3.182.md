# Release notes — v1.3.182

## Summary

**Industrial GET_BLOCKS past-tip end clamp (no simplifications):**

1. **GET_BLOCKS past-tip clamp** — inbound ranges with `to_height > local tip` (and valid `from_height`) clamp inclusive end to tip (`get_blocks_past_tip_clamp`).
2. Soft bandwidth/DoS honesty — no DB lookups for heights above local tip inside an otherwise valid window.
3. Sequel to v1.3.180 (future `from_height` refuse) / v1.3.181 (GET_BLOCK future refuse).

## Changes

- `network/p2p_node.py` — `_get_blocks_past_tip_clamp_end` in `_handle_get_blocks`
- Config: `p2p_get_blocks_past_tip_clamp` / `P2P_GET_BLOCKS_PAST_TIP_CLAMP` (default on)
- Metrics / security status gauge + clamp counter
- `node_version`: `1.3.182-industrial`

## Honesty

- Soft past-tip serve clamp — **not** tip proof, not Long-Range, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13182_get_blocks_past_tip_clamp.py -q
```
