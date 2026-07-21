# Release notes — v1.3.42

**Date:** 2026-07-21  
**Theme:** Native RocksDB typed key codecs

## Rust / hybrid

- `rocks_keycodec.rs` — `rocks_pack_u64` / `rocks_unpack_u64` + all Rocks key/prefix builders
- Byte-identical to `storage/keycodec.py` (symbolic genesis addresses preserved)
- `storage/keycodec.py` prefers abs_native with Python struct fallback

## Config

- `node_version`: `1.3.42-industrial`

## Tests / gates

- `tests/unit/test_v1342_rocks_keycodec.py` + existing `test_keycodec.py` / `test_rocks_store.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- P2P rate-limit table · full EVM host-in-apply · public mainnet
