# Release notes — v1.3.104

## Summary

**Native status payload gate:** on the native read path, `status` frames with a dict payload that fails `validate_status_inner` (same rules as Python `validate_p2p_status_payload`) are rejected with `bad_status_payload` before dispatch. Null status keepalives remain allowed.

## Changes

- `check_status_payload` in `p2p_transport.rs` (uses `validate_status_inner`)
- Status `native_status_gate`; metric `abs_p2p_native_status_gate`
- `node_version`: `1.3.104-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Strike/ban policy remains Python (`WireReject` → `_strike_peer_sync`)
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13104_p2p_native_status_gate.py -q
```
