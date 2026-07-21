# Release notes — v1.3.36

**Date:** 2026-07-21  
**Theme:** WASM/finality/reorg/RANDAO honesty + atomic ChainStorage replace

## Honesty / fail-closed

- WASM: `wasmtime_available` / `execution_bound` / `pseudo_token_host`; binary `\0asm` deploy rejected without wasmtime; `/status` exposes `wasm_operational`
- FinalityEngine on node is labeled standalone observer (`consensus_bound=false`); `/finality/stats` honesty fields
- Reorg predictor: no reserved `finalized` label → `heuristic_low_risk`; `model_only` / `not_consensus_finality`
- ValidatorSelection: `deterministic_hash_selection`, `FEATURE_VALIDATOR_SELECTION` off in prod, not commit/reveal RANDAO
- `ChainStorage.replace_chain` writes to temp dir then atomic swap (no delete-then-hope)

## Config

- `node_version`: `1.3.36-industrial`
- Prod default: `FEATURE_VALIDATOR_SELECTION=false`

## Tests / gates

- `tests/unit/test_v1336_honesty.py`
- Industrial gate needles for the above paths

## Explicit non-goals

- Real commit/reveal RANDAO · wasmtime mandatory for pseudo-token host · wiring standalone FinalityEngine into forge · public mainnet
