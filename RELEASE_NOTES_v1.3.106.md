# Release notes — v1.3.106

## Summary

**Native block sync shape gates:** on the native read path, `new_block` frames that fail `validate_block_announce_inner` are rejected with `bad_block_announce`, and `get_block` frames that fail `validate_get_block_inner` are rejected with `bad_get_block`, before Python dispatch. Block import / chain validation remain Python.

## Changes

- `check_block_announce_payload` / `check_get_block_payload` in `p2p_transport.rs`
- Status `native_block_sync_gate`; metric `abs_p2p_native_block_sync_gate`
- `node_version`: `1.3.106-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Shape-only; consensus / PoW / state application stay Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13106_p2p_native_block_sync_gate.py -q
```
