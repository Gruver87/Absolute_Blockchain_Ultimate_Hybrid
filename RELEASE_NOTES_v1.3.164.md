# Release notes — v1.3.164

## Summary

**Industrial GHOST ownership honesty (no simplifications):**

1. **GHOST head wire probe** — before reorg to fork-choice canonical head, solicit that hash via `get_block_by_hash`; refuse on empty / `ghost_head_probe_failed` / hash / height mismatch.
2. Sequel to v1.3.162 (fork peer-head probe) + v1.3.163 (reconcile fetched hash bind).

## Changes

- `network/p2p_node.py` — `_ghost_head_probe_refuse_reason` / `_reconcile_ghost_head` for NEW_BLOCK fork, `_reconcile_fork_at_peer`, `reconcile_peers`
- Config: `p2p_ghost_head_probe` / `P2P_GHOST_HEAD_PROBE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.164-industrial`

## Honesty

- Soft wire bind before GHOST reorg — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13164_ghost_head_probe.py -q
```
