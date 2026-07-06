# Release v1.2.23 — tx propagation Rocks reads + testnet gate

**Date:** 2026-07-06

## Summary

Complete tx propagation observability on Rocks hybrid path; add automated local testnet prerequisite checks.

## Changes

- `RocksChainStore.get_tx_propagation_trace` / `get_recent_tx_propagation`
- `scripts/testnet_readiness.ps1` (prod mesh health, harness, soak report)
- Tests: `tests/unit/test_rocks_tx_propagation.py`

## Test plan

- [x] `pytest tests/unit/test_rocks_tx_propagation.py`
- [x] `.\scripts\testnet_readiness.ps1 -ProdMesh -SkipIndustrialGate`
