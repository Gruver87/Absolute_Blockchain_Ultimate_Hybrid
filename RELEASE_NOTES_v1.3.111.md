# Release notes — v1.3.111

## Summary

**Native state-root shape gates:** on the native read path, `state_root_request` / `state_root_response` frames that fail the matching wire validators are rejected with `bad_state_root_request` / `bad_state_root_response` before Python dispatch. Root comparison / sync policy remain Python.

## Changes

- `check_state_root_request_payload` / `check_state_root_response_payload` in `p2p_transport.rs`
- Status `native_state_root_gate`; metric `abs_p2p_native_state_root_gate`
- `node_version`: `1.3.111-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Shape-only; state-root verify / fork choice stay Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13111_p2p_native_state_root_gate.py -q
```
