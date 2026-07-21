# Release notes — v1.3.38

**Date:** 2026-07-21  
**Theme:** Native GHOST fork-choice + simple block apply/replay kernels

## Rust / hybrid

- `ghost_select_head` / `ghost_cumulative_weight` / `ghost_chain_from_head` — pure GHOST in `abs_native`
- `lmd_compute_weights` — LMD stake aggregation
- `blockchain_apply_simple_block` — simple ABS transfers with fee burn + proposer fee + block reward (rejects EVM calldata)
- `blockchain_replay_simple_blocks` — multi-block reorg/tip-repair assist for simple chains
- Python: `consensus/ghost.py`, `consensus/lmd.py`, `core/blockchain.py` prefer native; EVM / errors fall back to Python

## Config

- `node_version`: `1.3.38-industrial`

## Tests / gates

- `tests/unit/test_v1338_native_kernels.py`
- `post_soak_verify` / industrial_gate needles for new symbols + wiring

## Explicit non-goals

- Full EVM apply inside Rust · finality/slashing kernels · eth_tx assembly · public mainnet · bridge ON without audited L1
