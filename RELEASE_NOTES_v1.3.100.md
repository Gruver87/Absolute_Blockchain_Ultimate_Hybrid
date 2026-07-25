# Release notes — v1.3.100

## Summary

**Native housekeeping payload gate:** when `auto_pong` is on, `ping`/`pong` payloads are fail-closed validated (parity with Python `_housekeeping_payload_ok`) *before* auto-keepalive consume/reply. `get_mempool`/`get_peers` are always gated on native read. Malformed ping no longer gets an automatic pong.

## Changes

- `housekeeping_payload_ok` / `check_housekeeping` in `p2p_transport.rs`
- Reject reason `bad_<type>_payload` preserved through `wire_fail_reason`
- Status `native_housekeeping_gate`; metric `abs_p2p_native_housekeeping_gate`
- `node_version`: `1.3.100-industrial`

## Honesty

- Still **not** full Rust message-loop ownership (dispatch / strikes / gossip remain Python)
- Still not libp2p / multiplex
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13100_p2p_native_housekeeping.py -q
```
