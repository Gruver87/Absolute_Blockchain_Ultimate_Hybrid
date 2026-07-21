# Release notes — v1.3.02

**Date:** 2026-07-21  
**Theme:** Post-soak industrial polish (Swiss-watch pass)

## Gates / honesty

- `industrial_gate` — correct `RocksChainStore` import (was false `RocksStore` warning)
- Wheel surface requires RocksEngine `column_families` + full P2P validator export list
- `.env.example` documents `ROCKSDB_*` + `ABS_REQUIRE_NATIVE_CRYPTO`

## P2P

- Shape-reject reason counters in `get_p2p_security_status()` (`shape_rejects`, `shape_rejects_total`)
- Housekeeping messages (`ping`/`pong`/`get_mempool`/`get_peers`) reject non-JSON-scalar noise

## Storage / native

- Rocks schema_version bumped to `rocksdb-chain-v2-cf` when CF mode enabled on legacy DB
- `sha256_hex_batch` / `double_sha256_hex` fail-closed when native crypto is required
- `node_version` default `1.3.02-industrial`

## Verify

```powershell
.\scripts\post_soak_verify.ps1
# or with rebuild:
.\scripts\post_soak_verify.ps1 -RebuildNative
```
