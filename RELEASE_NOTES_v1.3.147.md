# Release notes — v1.3.147

## Summary

**Industrial Rocks hot-path slice (no full store rewrite):**

1. **Typed account-row codec (`ABAR`)** — native `pack_account_row` / `unpack_account_row` for Rocks account values.
2. **Dual-read** — loads accept ABAR binary **or** legacy JSON; new writes prefer ABAR when native is present.
3. Wired through `RocksEngine` writeback commit, state-root blobs, and `account_view` decode.

## Changes

- `native/abs_native/src/account_row.rs` — ABAR v1 pack/unpack + dual-decode
- `storage/rocks_store.py` — `_pack_account_blob` / `_loads_account_blob_or_none`
- `state_trie` / `account_view` / `storage` — decode via `account_blob_to_value`
- `node_version`: `1.3.147-industrial`

## Honesty

- Soft account-value codec — **not** full Rocks rewrite, not block/tx blob migration, not `persist_block_atomic` in Rust, not public mainnet / tip proof / Long-Range / libp2p

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13147_account_row_codec.py -q
```
