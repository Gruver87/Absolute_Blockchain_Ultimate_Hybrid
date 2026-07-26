# Release notes — v1.3.168

## Summary

**Industrial same-height fork parent ownership honesty (no simplifications):**

1. **Fork peer-head parent bind** — after same-height peer.head wire probe, require probed `parent_hash` to match expected tip-height parent (`fork_peer_head_parent_mismatch`).
2. Sequel to v1.3.162 (fork peer-head probe) + v1.3.157 (catch-up contiguous parent).

## Changes

- `network/p2p_node.py` — parent check in `_fork_peer_head_probe_refuse_reason`
- Config: `p2p_fork_peer_head_parent_bind` / `P2P_FORK_PEER_HEAD_PARENT_BIND` (default on)
- Metrics / security status gauge; refuse counted via fork probe counter
- `node_version`: `1.3.168-industrial`

## Honesty

- Soft same-height sibling parent bind — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13168_fork_peer_head_parent_bind.py -q
```
