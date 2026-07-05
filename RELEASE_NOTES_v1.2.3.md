# Release v1.2.3 — RocksDB backup & restore

**Date:** 2026-07-05 · **API wave:** 61

## Summary

Production-grade chain data backup for the RocksDB hybrid layout, with CI disaster-recovery drill and honest storage documentation.

## Changes

- **`storage/chain_backup.py`** — checkpoint backup/restore (nested `data/chainstore/` and direct layouts)
- **`scripts/backup_chainstore.py`**, **`restore_chainstore.py`**, **`backup_chainstore.ps1`**
- **`scripts/backup_rocks_drill.py`** — CI DR roundtrip (skipped when native Rocks unavailable)
- **`docs/STORAGE_ROCKSDB.md`** — hybrid architecture, backup ops, roadmap
- **CI** — rocks drill + `test_rocks_*` / `test_chain_backup` in hybrid critical gate
- **Fix** — `RocksChainStore.backup_to()` no longer pre-creates checkpoint destination

## Usage

```powershell
# Local bind-mounted prod data
python scripts/backup_chainstore.py --data-dir data --dest backups/snap-1
python scripts/restore_chainstore.py --backup-dir backups/snap-1 --data-dir data --force --verify

# Running prod mesh node1
.\scripts\backup_chainstore.ps1 -DockerMesh1
```

## Not included

- Public mainnet launch
- Aux table migration into Rocks column families (P1 next)
- Automated 48h soak (operational checklist in STORAGE_ROCKSDB.md)
