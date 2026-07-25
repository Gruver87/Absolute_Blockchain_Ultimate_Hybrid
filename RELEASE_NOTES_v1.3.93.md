# Release notes — v1.3.93

## Summary

**Native write_message pump:** `P2PNativeConn.write_message` encodes a wire envelope and writes it in one Rust call. `PeerConnection._write_message` uses it on the native path when egress prepare is not required; with egress prepare, admit+encode stays on the Python/main thread then `write`.

## Changes

- `write_message(msg_type, data_json, allowed_types)` on `P2PNativeConn`
- Status `native_write_message`; metric `abs_p2p_native_write_message`
- `node_version`: `1.3.93-industrial`

## Honesty

- Still **not** full Rust message-loop ownership (handshake / dispatch / strikes / gossip remain Python)
- Still **not** libp2p / multiplex / async runtime
- Egress rate-limit still uses `p2p_egress_prepare` / `admit_egress` on the Python side (shared table is not taken into `to_thread`)
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1393_p2p_native_write_message.py -q
```
