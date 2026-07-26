# Release notes — v1.3.163

## Summary

**Industrial reconcile ownership honesty (no simplifications):**

1. **Reconcile fetched head hash bind** — after fetching the block for `target_head`, refuse reorg if returned hash ≠ target (`reconcile_head_hash_mismatch`). Covers GHOST + fork reconcile paths.
2. Sequel to v1.3.162 (fork peer-head wire probe) + v1.3.154 (catch-up peer-head probe).

## Changes

- `network/p2p_node.py` — `_reconcile_fetched_head_refuse_reason` in `_reconcile_to_head_hash`
- Config: `p2p_reconcile_head_hash_bind` / `P2P_RECONCILE_HEAD_HASH_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.163-industrial`

## Honesty

- Soft wire bind before reorg import — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13163_reconcile_head_hash_bind.py -q
```
