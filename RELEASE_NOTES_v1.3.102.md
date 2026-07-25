# Release notes — v1.3.102

## Summary

**Native I/O timeout config:** `p2p_native_io_timeout_ms` / `P2P_NATIVE_IO_TIMEOUT_MS` drives socket `SO_RCVTIMEO`/`SO_SNDTIMEO` via `P2PNativeConn.set_timeout_ms` after accept/connect, and aligns asyncio `wait_for` on the native read path. Rust exports `p2p_native_clamp_timeout_ms` (1000..600000 ms).

## Changes

- Config/env timeout knob; applied on inbound accept + outbound connect
- `io_timeout_ms` getter; connect uses `min(io_timeout, 15000)` for TCP connect
- Status + Prometheus `abs_p2p_native_io_timeout_ms`
- `node_version`: `1.3.102-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13102_p2p_native_io_timeout.py -q
```
