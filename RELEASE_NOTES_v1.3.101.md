# Release notes — v1.3.101

## Summary

**Native batch/chunk config knobs:** `p2p_native_read_batch`, `p2p_native_write_batch`, and `p2p_native_read_chunk` (plus env overrides) size the native read/write pumps. Rust exports `p2p_native_clamp_batch` / `p2p_native_clamp_chunk` so Python and the transport share the same 1..64 / 1024..1MiB bounds.

## Changes

- Config + env: `P2P_NATIVE_READ_BATCH` / `WRITE_BATCH` / `READ_CHUNK`
- Peer hooks copy clamped sizes; status + Prometheus gauges
- `p2p_native_clamp_batch` / `p2p_native_clamp_chunk` in `abs_native`
- `node_version`: `1.3.101-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13101_p2p_native_batch_config.py -q
```
