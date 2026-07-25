# Release notes — v1.3.54

**Date:** 2026-07-25  
**Theme:** EVM/mempool high-load soak harness (industrial load proof, not `/health/live`)

## Load / isolation proof

- `scripts/evm_mempool_load_harness.py` — concurrent mempool producers + serial `ChainApplyQueue.forge_and_apply`
- Mixed simple transfers + tiny EVM deploy bytecode
- Asserts height advance, forge success, receiver balance, apply queue counters
- Report: `data/evm_mempool_load_report.json`

## Config

- `node_version`: `1.3.54-industrial`

## Tests / gates

- `tests/unit/test_v1354_evm_mempool_load.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Public mainnet · tip satoshi root · bridge ON · nested CALL host-in-Rust (next) · multi-node Docker soak replacement
