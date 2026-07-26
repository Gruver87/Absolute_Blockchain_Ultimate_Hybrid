# Release notes — v1.3.174

## Summary

**Industrial NEW_BLOCK tip digest ownership honesty (no simplifications):**

1. **NEW_BLOCK tip-head bind** — after successful gossip import, when tip height equals announce height, local tip hash must match announce hash (`new_block_tip_head_mismatch`).
2. On mismatch: no attest / no rebroadcast; peer strike; refuse counter bumped.
3. Sequel to v1.3.172 (catch-up tip-head) + v1.3.173 (reconcile tip-head).

## Changes

- `network/p2p_node.py` — `_new_block_tip_head_refuse_reason` after `_import_block_async` in `_handle_new_block`
- Config: `p2p_new_block_tip_head_bind` / `P2P_NEW_BLOCK_TIP_HEAD_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.174-industrial`

## Honesty

- Soft tip digest bind at gossip accept — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13174_new_block_tip_head_bind.py -q
```
