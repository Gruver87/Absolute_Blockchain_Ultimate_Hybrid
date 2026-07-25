# Release notes — v1.3.112

## Summary

**Native cross-shard shape gates:** on the native read path, `cross_shard_tx` / `cross_shard_ack` / `shard_migration` frames that fail the matching wire validators are rejected with `bad_cross_shard_tx` / `bad_cross_shard_ack` / `bad_shard_migration` before Python dispatch. Shard apply policy remains Python.

## Changes

- `check_cross_shard_tx_payload` / `check_cross_shard_ack_payload` / `check_shard_migration_payload` in `p2p_transport.rs`
- Status `native_cross_shard_gate`; metric `abs_p2p_native_cross_shard_gate`
- `node_version`: `1.3.112-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Shape-only; cross-shard execution / balances stay Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13112_p2p_native_cross_shard_gate.py -q
```
