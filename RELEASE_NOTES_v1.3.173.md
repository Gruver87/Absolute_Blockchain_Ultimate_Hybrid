# Release notes — v1.3.173

## Summary

**Industrial reconcile tip digest ownership honesty (no simplifications):**

1. **Reconcile tip-head bind** — after successful reorg/import, local tip hash must match `target_head` (`reconcile_tip_head_mismatch`).
2. Sequel to v1.3.163 (fetched body hash bind) + v1.3.172 (catch-up tip-head bind) — reorg success cannot greenwash without tip digest ownership.

## Changes

- `network/p2p_node.py` — `_reconcile_tip_head_refuse_reason` after `_reorg_and_import_async`
- Config: `p2p_reconcile_tip_head_bind` / `P2P_RECONCILE_TIP_HEAD_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.173-industrial`

## Honesty

- Soft tip digest bind at reconcile choke point — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13173_reconcile_tip_head_bind.py -q
```
