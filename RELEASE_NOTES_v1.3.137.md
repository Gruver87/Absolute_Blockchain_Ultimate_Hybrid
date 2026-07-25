# Release notes — v1.3.137

## Summary

**Industrial mesh/consensus honesty (no simplifications):**

1. **Attestation local-head consistency** — when `target_hash` is already known locally, `target_height` must match the local header height (`attestation_local_height_mismatch`). Unknown hashes are still allowed (soft).
2. **Solicit-only block responses** — unsolicited `MSG_BLOCKS` / `MSG_BLOCK` are struck (`unsolicited_blocks` / `unsolicited_block`) and never steer sync; only active get_blocks / get_block waiters fulfill.

## Changes

- `_attestation_local_head_reject_reason` after slot-ahead gate
- Waiter + free-path solicit-only for block/blocks (mirrors mempool v1.3.131)
- Metrics: `native_attestation_local_head`, `attestation_local_head_rejects_total`, `native_block_solicit_only`, `unsolicited_block_rejects_total`
- `node_version`: `1.3.137-industrial`

## Honesty

- Soft local consistency when header known — **not** attestation↔canonical crypto binding, not tip proof, not fork-choice ownership, not libp2p, not ceremony / external audit / public mainnet

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13137_p2p_attestation_local_and_block_solicit.py -q
```
