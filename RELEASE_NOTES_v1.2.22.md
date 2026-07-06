# Release v1.2.22 — native Rocks account scan for state root

**Date:** 2026-07-06

## Summary

State root computation on prod RocksDB no longer materializes all account blobs in Python for cold scans.

## Changes

- `RocksEngine.state_root_from_account_prefix(prefix, limit)` in `abs_native`
- `RocksChainStore.compute_state_root` delegates to native scan when incremental accumulator is empty
- Test: `tests/unit/test_rocks_state_root_scan.py`

## Test plan

- [x] `pytest tests/unit/test_rocks_state_root_scan.py tests/unit/test_state_root_native.py`
- [ ] Rebuild native wheel in CI / prod Docker image
