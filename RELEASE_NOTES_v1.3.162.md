# Release notes — v1.3.162

## Summary

**Industrial same-height fork ownership honesty (no simplifications):**

1. **Fork peer-head wire probe** — before same-height reorg to `peer.head`, solicit that hash via `get_block_by_hash`; refuse on empty head / `fork_peer_head_probe_failed` / hash / height mismatch.
2. Sequel to v1.3.154 (catch-up peer-head probe) + v1.3.139 (require head for ahead catch-up).

## Changes

- `network/p2p_node.py` — `_fork_peer_head_probe_refuse_reason` in `_reconcile_fork_at_peer`
- Config: `p2p_fork_peer_head_probe` / `P2P_FORK_PEER_HEAD_PROBE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.162-industrial`

## Honesty

- Soft wire bind before fork reorg — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13162_fork_peer_head_probe.py -q
```
