# Release notes — v1.3.159

## Summary

**Industrial height-cap tip honesty (no simplifications):**

1. clear fantasy head on height-cap — when STATUS / NEW_BLOCK / handshake claims are capped above the local tip window, `peer.head` is cleared (not left pointing at a prior fantasy tip).
2. Parity with handshake soft ownership from v1.3.135; STATUS/NEW_BLOCK previously skipped head install but kept old head.

## Changes

- `network/p2p_node.py` — clear `peer.head` on capped STATUS / NEW_BLOCK / handshake
- Config: `p2p_height_cap_clear_head` / `P2P_HEIGHT_CAP_CLEAR_HEAD` (default on)
- Metrics / security status gauge
- `node_version`: `1.3.159-industrial`

## Honesty

- Soft tip-meta ownership — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13159_height_cap_clear_head.py -q
```
