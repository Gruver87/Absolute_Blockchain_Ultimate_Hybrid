# Release notes — v1.3.149

## Summary

**Industrial Rocks hot-path slice (block values, no full store rewrite):**

1. **Typed block-row codec (`ABLK`)** — native `pack_block_row` / `unpack_block_row` for Rocks block-height values.
2. **Header typed + nested JSON** — scalars packed binary; `transactions` and unknown extras stay length-prefixed JSON for replay/open-schema.
3. **Dual-read** — loads accept ABLK binary **or** legacy JSON; new writes prefer ABLK when native is present.

## Changes

- `native/abs_native/src/block_row.rs` — ABLK v1 pack/unpack + dual-decode
- `storage/rocks_store.py` — `_pack_block_blob` / `_loads_block_blob_or_none`
- `node_version`: `1.3.149-industrial`

## Honesty

- Soft **block-value** codec — **not** full nested-tx binary migration, not receipts, not `persist_block_atomic` in Rust, not tip proof / Long-Range / libp2p / public mainnet / full Rocks rewrite
- Does not change canonical block hashing — storage shape only

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13149_block_row_codec.py -q
```
