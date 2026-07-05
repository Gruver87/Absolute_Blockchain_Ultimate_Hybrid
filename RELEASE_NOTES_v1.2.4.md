# Release v1.2.4 — RocksDB tuning & DR rehearsal

**Date:** 2026-07-05 · **API wave:** 61

## Summary

Configurable RocksDB block cache / write buffers, LSM metrics in `get_stats()`, and a safe DR rehearsal script.

## Changes

- **`RocksEngine`** — `block_cache_mb`, `write_buffer_mb`, `storage_properties()`, `tuning_config()`
- **Config** — `ROCKSDB_BLOCK_CACHE_MB` (default 256), `ROCKSDB_WRITE_BUFFER_MB` (default 64)
- **`scripts/dr_restore_rehearsal.ps1`** — backup → temp restore → verify (live data untouched)
- **`docs/STORAGE_ROCKSDB.md`** — aux.db permanent scope table

## Usage

```powershell
# DR rehearsal on local data
.\scripts\dr_restore_rehearsal.ps1 -DataDir data

# Prod mesh node1 snapshot rehearsal
.\scripts\dr_restore_rehearsal.ps1 -DockerMesh1
```

## Not included

- Aux table migration to Rocks CF
- Public mainnet launch
