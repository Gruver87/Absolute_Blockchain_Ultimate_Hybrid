# Release notes — v1.3.46

**Date:** 2026-07-25  
**Theme:** Mixed simple+EVM native apply (Priority 18)

## Hybrid

- Mixed blocks (simple transfer + EVM calldata) use native `blockchain_apply_host_effects`
- Per-tx apply with `reward=0` so EVM host sees prior balance updates; final native reward
- Simple txs: `apply_value=True`; EVM: Python host then `apply_value=False`
- `create_block` multi-tx same-sender: `validate_transaction(expected_nonce=…)` honors nonce cursor

## Config

- `node_version`: `1.3.46-industrial`

## Tests / gates

- `tests/unit/test_v1346_mixed_apply.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Deeper CALL host inside Rust · public mainnet · bridge L1 ON without audited contracts
