# Release v1.2.20 — NFT tokens on Rocks

**Date:** 2026-07-06

## Summary

P1 storage: `nft_tokens` persist in RocksDB on prod hybrid; signed tx smoke verified on live mesh.

## Added

- Rocks keys `P_NFT_TOKEN` for NFT token registry
- Hybrid migration `aux_nft_tokens_migrated_v1` from aux.db
- `tests/unit/test_rocks_nft_tokens.py`

## Verified

- Prod signed tx: mempool propagation to node2/node3 OK (live mesh height≥2)
- Mining resumes after v1.2.19 (mesh height growing)

## Soak (your 7h run)

```powershell
.\scripts\soak_monitor.ps1 -ProdMesh -Hours 7 -IntervalSec 300
```
