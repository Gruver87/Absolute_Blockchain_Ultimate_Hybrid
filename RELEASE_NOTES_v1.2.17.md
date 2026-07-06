# Release v1.2.17 — monitoring + soak

**Date:** 2026-07-06

## Summary

Industrial observability: fast health polls, mesh alignment checks, and 24h+ soak runner for prod mesh.

## Changes

- **`/chain/consistency/harness?quick=1`** — 3s peer timeout for monitoring (full scan still default)
- **`health_watch.ps1`** — quick/full cycles (full every 6th), mesh height/head alignment, fixed `failed_checks` handling
- **`soak_monitor.ps1`** — long-running soak with JSON report (`logs/soak_report.json`)

## Test plan

- [x] `pytest tests/unit/test_wave54_state_consistency.py`
- [x] `.\scripts\health_watch.ps1 -ProdMesh -DurationMin 1` — all green
- [ ] `.\scripts\soak_monitor.ps1 -ProdMesh -Hours 24` (optional overnight)

## Usage

```powershell
.\scripts\health_watch.ps1 -ProdMesh
.\scripts\soak_monitor.ps1 -ProdMesh -Hours 24 -IntervalSec 300
```
