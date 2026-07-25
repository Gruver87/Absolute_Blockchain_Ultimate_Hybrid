# Release notes — v1.3.122

## Summary

**Native singular `block` response hash ingress:** on the message-loop shell, non-null `block` payloads are canonical-hash checked (same verifier as `new_block` / `blocks`). `null` remains a valid not-found response.

## Changes

- `check_block_payload_semantics` on `read_message_loop_events` (null → OK; else `verify_block_announce_semantics_inner`)
- Strike: `bad_block_hash` (shape: `bad_block_payload`)
- Status: `native_block_payload_semantic_gate`
- Metrics: `abs_p2p_native_block_payload_semantic_gate` (rejects fold into `block_semantic_rejects_total`)
- `node_version`: `1.3.122-industrial`

## Honesty

- Still **not** request/hash correlation, import, fork-choice, full message-loop, or libp2p
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13122_p2p_native_block_payload_semantic_gate.py -q
```
