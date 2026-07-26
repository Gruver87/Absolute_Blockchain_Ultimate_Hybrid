# Release notes — v1.3.157

## Summary

**Industrial catch-up contiguous extension honesty (no simplifications):**

1. **Peer-head parent bind (+1)** — when peer claims exactly `local_height + 1`, probed `peer.head` `parent_hash` must match local tip (`catch_up_peer_head_parent_mismatch`).
2. Sequel to v1.3.154 (peer-head wire probe) + v1.3.146 (local tip probe).

## Changes

- `network/p2p_node.py` — contiguous parent check inside `_catch_up_peer_head_probe_refuse_reason`
- Config: `p2p_catch_up_peer_head_parent_bind` / `P2P_CATCH_UP_PEER_HEAD_PARENT_BIND` (default on)
- Metrics / security status gauge
- `node_version`: `1.3.157-industrial`

## Honesty

- Soft contiguous extension bind — **not** tip existence proof, not root-belongs-to-head merkle, not Long-Range / weak-subjectivity checkpoint, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
.\scripts\check_all.ps1 -Mode Standard
python -m pytest tests/unit/test_v13157_catch_up_peer_head_parent_bind.py -q
```
