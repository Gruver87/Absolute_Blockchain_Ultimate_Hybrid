# Release notes — v1.3.116

## Summary

**Native message-loop event shell:** `P2PNativeConn.read_message_loop_events` returns ordered `dispatch` / `strike` / `keepalive` / `idle` / `eof` events so Python `_message_loop` can consume a fused batch without dropping valid frames before a reject. Application handlers, rate/ban tables, and peer lifecycle stay Python — **not** full Rust message-loop ownership.

## Changes

- Rust `read_message_loop_events` (preserves dispatch-then-strike ordering)
- Python `PeerConnection.recv_loop_events` + `_message_loop` shell path
- Status: `native_message_loop_shell`, dispatch/strike totals
- Metrics: `abs_p2p_native_message_loop_shell`, `_dispatch_total`, `_strikes_total`
- `node_version`: `1.3.116-industrial`

## Honesty

- Still **not** full Rust message-loop / libp2p / application dispatch
- Strike **policy** (ban thresholds) and `_handle_message` remain Python
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13116_p2p_native_message_loop_shell.py -q
```
