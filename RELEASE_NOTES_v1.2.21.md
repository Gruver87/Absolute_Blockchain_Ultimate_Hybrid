# Release v1.2.21 — NFT Rocks migration + soak fix

**Date:** 2026-07-06

## Summary

Complete NFT marketplace persistence on RocksDB hybrid path; fix long-running soak monitor parameter binding.

## Changes

- Rocks keys: `nft_offers`, `nft_auctions`, `nft_sales` + one-shot aux migrations
- `soak_monitor.ps1`: hashtable splat to `health_watch`; stricter JSON report pass criteria
- Reorg/live state-root invariant tests in `test_rocks_reorg_meta.py`

## Test plan

- [x] `pytest tests/unit/test_rocks_nft_market.py tests/unit/test_rocks_reorg_meta.py`
- [ ] Overnight prod mesh soak (`soak_monitor.ps1 -ProdMesh -Hours 10`)
