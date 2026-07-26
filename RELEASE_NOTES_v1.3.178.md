# Release notes — v1.3.178

## Summary

**Industrial GET_MEMPOOL tip-alignment honesty (no simplifications):**

1. **Mempool serve tip-align** — inbound `GET_MEMPOOL` dumps are refused when `|peer.height - local| > max_delta` (default 2) (`get_mempool_tip_misaligned`).
2. Far peers get an empty mempool response (no 200-tx serialization) — soft bandwidth/DoS honesty.
3. Same window as outbound `_sync_mempool_with_peer` pull gate.

## Changes

- `network/p2p_node.py` — `_get_mempool_tip_align_refuse_reason` in `_handle_get_mempool`
- Config: `p2p_mempool_serve_tip_align` / `P2P_MEMPOOL_SERVE_TIP_ALIGN` (default on)
- Config: `p2p_mempool_serve_max_height_delta` / `P2P_MEMPOOL_SERVE_MAX_HEIGHT_DELTA` (default 2)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.178-industrial`

## Honesty

- Soft tip-alignment for mempool dump serve — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust fee scheduler

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13178_mempool_serve_tip_align.py -q
```
