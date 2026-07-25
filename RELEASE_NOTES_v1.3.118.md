# Release notes — v1.3.118

## Summary

**Native `new_tx` signature ingress:** on the message-loop shell, singular `new_tx` frames are signature-checked in Rust with the node's trusted `chain_id` injected into the canonical preimage (parity with `Wallet._canonical_tx_for_hash`). Mempool batch, nonce/balance, and identity-from-binding stay Python.

## Changes

- `verify_wire_tx_signature_inner` + `check_wire_tx_semantics` on `read_message_loop_events`
- Optional kwargs: `expected_chain_id`, `require_tx_signatures`
- Strike reasons: `missing_tx_signature` / `missing_tx_public_key` / `bad_tx_signature`
- Status: `native_tx_semantic_gate`, `tx_semantic_rejects_total`
- Metrics: `abs_p2p_native_tx_semantic_gate`, `abs_p2p_tx_semantic_rejects_total`
- `node_version`: `1.3.118-industrial`

## Honesty

- Still **not** full Rust message-loop / libp2p / mempool-batch semantics
- Nonce, balance, fees, deploy policy remain Python
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13118_p2p_native_tx_semantic_gate.py -q
```
