# Release notes — v1.3.44

**Date:** 2026-07-21  
**Theme:** EVM host-in-apply fee effects (native economics after Python host)

## Rust / hybrid

- `blockchain_apply_host_effects` — fee / burn / miner / nonce / reward on account snapshot
- All-EVM blocks: Python EVM host mutates storage/code/value; native applies economics
- `core/blockchain.py` prefers host-effects path when every tx has calldata

## Config

- `node_version`: `1.3.44-industrial`

## Tests / gates

- `tests/unit/test_v1344_evm_host_apply.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Mixed simple+EVM single native apply · full CALL host inside Rust · public mainnet
