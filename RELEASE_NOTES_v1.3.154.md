# Release notes — v1.3.154

## Summary

**Industrial catch-up ownership honesty (no simplifications):**

1. **Peer-head wire probe** — before ahead `get_blocks`, solicit claimed `peer.head` via `get_block_by_hash`; refuse on `catch_up_peer_head_probe_failed`, hash mismatch, or height mismatch.
2. Sequel to v1.3.139 (require head) + v1.3.146 (local tip probe + local head↔height bind) + v1.3.153 (NEW_BLOCK bind).

## Changes

- `network/p2p_node.py` — `_catch_up_peer_head_probe_refuse_reason` before sync download
- Config: `p2p_catch_up_peer_head_probe` / `P2P_CATCH_UP_PEER_HEAD_PROBE` (default on)
- Metrics / security status gauges + refuse counter
- `node_version`: `1.3.154-industrial`

## Honesty

- Soft scheduling / wire bind — **not** tip existence proof, not root-belongs-to-head merkle, not Long-Range / weak-subjectivity checkpoint, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
.\scripts\check_all.ps1 -Mode Standard
python -m pytest tests/unit/test_v13154_catch_up_peer_head_probe.py -q
```
