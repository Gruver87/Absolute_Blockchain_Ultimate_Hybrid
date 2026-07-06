# Release v1.2.26 — prod EVM evidence scripts

**Date:** 2026-07-06

## Summary

Close the "prod EVM not ops-proven" gap with a runnable smoke script and unified evidence suite.

## Changes

- `scripts/prod_evm_smoke.py` — `/contract/deploy` + `eth_getCode` + `eth_getStorageAt` on :18546–:18548
- `scripts/prod_evidence_suite.ps1` — health + failover + signed tx + EVM
- Fix `prod_signed_tx_smoke.py` missing `time` import
- Tests: `tests/unit/test_prod_evm_smoke.py`

## Test plan

- [x] `pytest tests/unit/test_prod_evm_smoke.py`
- [ ] Live: `python scripts/prod_evm_smoke.py` (mesh up, `.env` with `RPC_API_KEYS`)
