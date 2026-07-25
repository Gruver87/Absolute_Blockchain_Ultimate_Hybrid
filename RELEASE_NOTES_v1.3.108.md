# Release notes — v1.3.108

## Summary

**Native tx gossip shape gates:** on the native read path, `new_tx` frames that fail `validate_wire_tx_inner` are rejected with `bad_wire_tx`, and `mempool` frames that fail `validate_mempool_batch_inner` are rejected with `bad_mempool_batch`, before Python dispatch. Signature / mempool admission remain Python.

## Changes

- `check_wire_tx_payload` / `check_mempool_batch_payload` in `p2p_transport.rs`
- Unified `check_ingress_shape_gates` helper on read path
- Status `native_tx_gossip_gate`; metric `abs_p2p_native_tx_gossip_gate`
- `node_version`: `1.3.108-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Shape-only; tx sig verify / mempool policy stay Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13108_p2p_native_tx_gossip_gate.py -q
```
