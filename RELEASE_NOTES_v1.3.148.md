# Release notes — v1.3.148

## Summary

**Industrial Rocks hot-path slice (tx values, no full store rewrite):**

1. **Typed tx-row codec (`ATXV`)** — native `pack_tx_row` / `unpack_tx_row` for Rocks `P_TX` values.
2. **Dual-read** — loads accept ATXV binary **or** legacy JSON; new writes prefer ATXV when native is present.
3. Wired through insert, point get, block/recent/address scans, iter, and reorg truncate.

## Changes

- `native/abs_native/src/tx_row.rs` — ATXV v1 pack/unpack + dual-decode
- `storage/rocks_store.py` — `_pack_tx_blob` / `_loads_tx_blob_or_none`
- `node_version`: `1.3.148-industrial`

## Honesty

- Soft **tx-value** codec — **not** block blob (`ABLK`), not receipts, not `persist_block_atomic` in Rust, not tip proof / Long-Range / libp2p / public mainnet / full Rocks rewrite
- Does not change wire/consensus tx hashing — storage shape only

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13148_tx_row_codec.py -q
```
