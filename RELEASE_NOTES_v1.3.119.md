# Release notes — v1.3.119

## Summary

**Native `mempool` batch signature ingress:** on the message-loop shell, each transaction in a `mempool` batch is signature-checked in Rust with the node's trusted `chain_id` (reuses `verify_wire_tx_signature_inner`). Nonce/balance/ingest and full dispatch stay Python.

## Changes

- `verify_mempool_batch_signatures_inner` + `check_mempool_batch_semantics` on `read_message_loop_events`
- Same strike reasons as new_tx: `missing_tx_signature` / `missing_tx_public_key` / `bad_tx_signature` (plus shape `bad_mempool_batch`)
- Status: `native_mempool_semantic_gate`
- Metrics: `abs_p2p_native_mempool_semantic_gate` (rejects fold into `abs_p2p_tx_semantic_rejects_total`)
- `node_version`: `1.3.119-industrial`

## Honesty

- Still **not** full Rust message-loop / libp2p / mempool ingest ownership
- Nonce, balance, fees, deploy policy remain Python
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13119_p2p_native_mempool_semantic_gate.py -q
```
