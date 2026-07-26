# Release notes — v1.3.155

## Summary

**Industrial tip-meta ownership honesty (no simplifications):**

1. **STATUS/handshake known-head height bind** — if claimed `head_hash` is already known locally, claimed height must match that header (`status_head_height_mismatch` / `handshake_head_height_mismatch`).
2. Shared helper `_local_known_head_height_mismatch` also backs NEW_BLOCK bind (v1.3.153).
3. Sequel to v1.3.153 (NEW_BLOCK) + v1.3.146 (catch-up local bind).

## Changes

- `network/p2p_node.py` — refuse before installing peer tip from status/handshake
- Config: `p2p_status_head_height_bind` / `P2P_STATUS_HEAD_HEIGHT_BIND` (default on)
- Metrics / security status gauges + mismatch counter
- `node_version`: `1.3.155-industrial`

## Honesty

- Soft scheduling / local bind — **not** tip existence proof, not root-belongs-to-head merkle, not Long-Range / weak-subjectivity checkpoint, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
.\scripts\check_all.ps1 -Mode Standard
python -m pytest tests/unit/test_v13155_status_head_height_bind.py -q
```
