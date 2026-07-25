# Release notes — v1.3.95

## Summary

**Native batch write pumps:** `P2PNativeConn.write_messages` (encode+write) and `write_payloads` (pre-encoded). `PeerConnection._send_loop` drains up to N queued envelopes into one native hop via `_write_messages_batch`.

## Changes

- `write_messages(items, allowed_types)` and `write_payloads(payloads)` on `P2PNativeConn`
- Send-queue batch drain (`_native_write_batch`, default 8)
- Status `native_write_messages`; metric `abs_p2p_native_write_messages`
- `node_version`: `1.3.95-industrial`

## Honesty

- Still **not** full Rust message-loop ownership (handshake / dispatch / strikes / gossip remain Python)
- Still **not** libp2p / multiplex / async runtime
- Egress prepare/admit still runs on the Python side before `write_payloads`
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1395_p2p_native_write_messages.py -q
```
