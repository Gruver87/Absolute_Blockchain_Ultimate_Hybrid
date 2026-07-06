# Release v1.2.18 — industrial gate + Rocks evm_logs

**Date:** 2026-07-06

## Summary

P0 industrial hardening: failover drill, signed tx smoke, unified gate script; evm_logs on RocksDB hot path.

## Added

- `scripts/prod_mesh_failover.ps1` — prod mesh node2 stop/start recovery (`verify_p2p_ci --mode prod-mesh3-recovery`)
- `scripts/prod_signed_tx_smoke.py` — live signed transfer (no auto_sign)
- `scripts/prod_mesh_industrial.ps1` — health → failover → signed tx → optional soak
- RocksDB `evm_logs` keys (`P_EVM_LOG`, `P_EVM_LOG_TX`) + aux migration on hybrid open

## Fixed

- Recovery drill accepts peer-count fallback when topology reports `under_mesh`
- `health_watch.ps1` / `prod_mesh_industrial.ps1` exit codes for PowerShell callers

## Usage

```powershell
.\scripts\prod_mesh_industrial.ps1
.\scripts\prod_mesh_failover.ps1
python scripts/prod_signed_tx_smoke.py
.\scripts\prod_mesh_industrial.ps1 -RunSoak -SoakHours 24 -SkipFailover -SkipTx
```
