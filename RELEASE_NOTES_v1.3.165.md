# Release notes — v1.3.165

## Summary

**Industrial reconcile contiguous ownership honesty (no simplifications):**

1. **Reconcile contiguous parent bind** — when fetched head height is exactly `local+1`, `parent_hash` must match local tip (`reconcile_contiguous_parent_mismatch`).
2. Sequel to v1.3.163 (reconcile hash bind) + v1.3.157 / v1.3.160 (catch-up / NEW_BLOCK contiguous parent).

## Changes

- `network/p2p_node.py` — `_reconcile_contiguous_parent_refuse_reason` in `_reconcile_to_head_hash`
- Config: `p2p_reconcile_contiguous_parent_bind` / `P2P_RECONCILE_CONTIGUOUS_PARENT_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.165-industrial`

## Honesty

- Soft contiguous extension bind — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13165_reconcile_contiguous_parent_bind.py -q
```
