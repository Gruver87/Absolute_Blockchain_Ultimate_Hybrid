# Release notes — v1.3.92

## Summary

**Native framed read + wire-parse pump:** `P2PNativeConn.read_message` returns a decoded `{type, data}` envelope in one Rust call (frame + parse). `PeerConnection.recv` uses it on the native transport path; rate-limit admit stays on the Python side when ingress is enabled.

## Changes

- `read_message(chunk_sz, allowed_types)` on `P2PNativeConn`
- Status `native_read_message`; metric `abs_p2p_native_read_message`
- `node_version`: `1.3.92-industrial`

## Honesty

- Still **not** full Rust message-loop ownership (handshake / dispatch / strikes / gossip remain Python)
- Still **not** libp2p / multiplex / async runtime
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1392_p2p_native_read_message.py -q
```
