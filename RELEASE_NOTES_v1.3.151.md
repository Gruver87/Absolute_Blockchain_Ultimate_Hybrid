# Release notes — v1.3.151

## Summary

**Industrial Rocks hot-path slice (receipt values, no full store rewrite):**

1. **Typed receipt-row codec (`ATXR`)** — native `pack_receipt_row` / `unpack_receipt_row` for Rocks `P_TX_RECEIPT` values.
2. **Dual-read** — loads accept ATXR binary **or** legacy JSON; new writes prefer ATXR when native is present.
3. Wired through insert, point get, and reorg truncate.

## Changes

- `native/abs_native/src/receipt_row.rs` — ATXR v1 pack/unpack + dual-decode
- `storage/rocks_store.py` — `_pack_receipt_blob` / `_loads_receipt_blob_or_none`
- `node_version`: `1.3.151-industrial`

## Honesty

- Soft **receipt-value** codec — **not** tip proof / Long-Range / libp2p / public mainnet / full Rocks rewrite
- Completes the soft Rocks value-codec set: accounts (`ABAR`) + txs (`ATXV`) + blocks (`ABLK`) + receipts (`ATXR`)

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13151_receipt_row_codec.py -q
```
