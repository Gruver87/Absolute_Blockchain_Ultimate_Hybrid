# Release notes — v1.3.103

## Summary

**Native mid-session handshake gate:** after a successful handshake, Python marks `P2PNativeConn.session_established`. Further `handshake` / `handshake_ack` frames on the native read path are rejected with `mid_session_handshake` (WireReject → strike), matching the Python `_handle_message` fail-closed rule.

## Changes

- `set_session_established` / `session_established` on `P2PNativeConn`
- `check_mid_session_handshake` in `read_message` / `read_messages`
- `_do_handshake` marks session; `_message_loop` bumps `handshake_rejects` on native reject
- Status `native_mid_session_gate`; metric `abs_p2p_native_mid_session_gate`
- `node_version`: `1.3.103-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Strike/ban policy remains Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13103_p2p_native_mid_session.py -q
```
