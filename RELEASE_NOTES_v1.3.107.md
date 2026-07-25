# Release notes — v1.3.107

## Summary

**Native block fetch shape gates:** on the native read path, `get_blocks` / `get_block_by_hash` / `blocks` frames that fail the matching wire validators are rejected with `bad_get_blocks` / `bad_get_block_by_hash` / `bad_blocks_batch` before Python dispatch. Chain import remains Python.

## Changes

- `check_get_blocks_payload` / `check_get_block_by_hash_payload` / `check_blocks_batch_payload` in `p2p_transport.rs`
- Status `native_block_fetch_gate`; metric `abs_p2p_native_block_fetch_gate`
- `node_version`: `1.3.107-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Shape-only; sync apply / consensus stay Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13107_p2p_native_block_fetch_gate.py -q
```
