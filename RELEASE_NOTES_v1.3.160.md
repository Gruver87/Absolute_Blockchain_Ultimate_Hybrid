# Release notes — v1.3.160

## Summary

**Industrial NEW_BLOCK contiguous extension honesty (no simplifications):**

1. **Contiguous parent bind (+1)** — when announce height is exactly `local_height + 1`, parsed `parent_hash` must match local tip (`new_block_contiguous_parent_mismatch`) before tip mutate.
2. Sequel to v1.3.156 (announce↔body) + v1.3.157 (catch-up peer-head parent bind).

## Changes

- `network/p2p_node.py` — `_new_block_contiguous_parent_refuse_reason` before tip mutate
- Config: `p2p_new_block_contiguous_parent_bind` / `P2P_NEW_BLOCK_CONTIGUOUS_PARENT_BIND` (default on)
- Metrics / security status gauge + mismatch counter
- `node_version`: `1.3.160-industrial`

## Honesty

- Soft contiguous extension bind — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13160_new_block_contiguous_parent_bind.py -q
```
