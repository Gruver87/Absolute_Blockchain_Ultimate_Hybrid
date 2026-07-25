# Release notes — v1.3.113

## Summary

**Native handshake payload gate:** on `handshake_roundtrip`, inbound `handshake` / `handshake_ack` frames that fail `validate_handshake_inner` are rejected with `bad_handshake_payload` before Python policy. Chain-id / TLS identity / `accepted` handling remain Python.

## Changes

- `check_handshake_payload` in `p2p_transport.rs` (wired into `handshake_roundtrip`)
- Status `native_handshake_payload_gate`; metric `abs_p2p_native_handshake_payload_gate`
- `node_version`: `1.3.113-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Shape-only on handshake I/O fuse; policy stay Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13113_p2p_native_handshake_payload_gate.py -q
```
