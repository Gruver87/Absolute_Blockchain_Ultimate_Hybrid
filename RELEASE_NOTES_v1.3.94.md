# Release notes — v1.3.94

## Summary

**Native batch `read_messages` pump:** `P2PNativeConn.read_messages` drains up to N decoded envelopes in one Rust call. `PeerConnection.recv` queues them in `_pending_msgs` to cut `to_thread` overhead on the hot path.

## Changes

- `read_messages(max_n, chunk_sz, allowed_types)` on `P2PNativeConn`
- Partial batch on mid-drain timeout (success with messages already read)
- Status `native_read_messages`; metric `abs_p2p_native_read_messages`
- `node_version`: `1.3.94-industrial`

## Honesty

- Still **not** full Rust message-loop ownership (handshake / dispatch / strikes / gossip remain Python)
- Still **not** libp2p / multiplex / async runtime
- Rate-limit admit still runs per message on the Python side
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1394_p2p_native_read_messages.py -q
```
