# Release notes — v1.3.166

## Summary

**Industrial handshake ownership honesty (no simplifications):**

1. **Handshake head requires positive height** — head-only handshake (`height<=0` + `head_hash`) refused when local tip `> 0` (`handshake_head_without_height`).
2. Sequel / parity with v1.3.161 (STATUS head requires height).

## Changes

- `network/p2p_node.py` — `_handshake_head_without_height_refuse_reason` in `_do_handshake`
- Config: `p2p_handshake_head_requires_height` / `P2P_HANDSHAKE_HEAD_REQUIRES_HEIGHT` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.166-industrial`

## Honesty

- Soft head↔height ownership at handshake — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13166_handshake_head_requires_height.py -q
```
