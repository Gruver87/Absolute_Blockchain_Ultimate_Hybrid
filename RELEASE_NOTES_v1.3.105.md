# Release notes — v1.3.105

## Summary

**Native attestation shape gate:** on the native read path, `attestation` frames that fail `validate_attestation_shape_inner` (same rules as Python `validate_p2p_attestation_payload`) are rejected with `bad_attestation_shape` before dispatch. Signature verification remains Python.

## Changes

- `check_attestation_payload` in `p2p_transport.rs`
- Status `native_attestation_gate`; metric `abs_p2p_native_attestation_gate`
- `node_version`: `1.3.105-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Attestation **signature** verify stays Python; this is shape-only
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13105_p2p_native_attestation_gate.py -q
```
