# Release notes — v1.3.109

## Summary

**Native singular `block` payload gate:** on the native read path, `block` frames with non-null data that fail `validate_block_announce_inner` are rejected with `bad_block_payload`. Null/`None` remains allowed (not-found response), matching Python.

## Changes

- `check_block_payload` in `p2p_transport.rs` (wired via `check_ingress_shape_gates`)
- Status `native_block_payload_gate`; metric `abs_p2p_native_block_payload_gate`
- `node_version`: `1.3.109-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Shape-only; chain apply stays Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13109_p2p_native_block_payload_gate.py -q
```
