# Release notes — v1.3.49

**Date:** 2026-07-25  
**Theme:** Nested CALL frame decode planner (Priority 21)

## Rust / hybrid

- `evm_decode_nested_call_frame` — pure CALL/CALLCODE/DELEGATECALL/STATICCALL stack-frame decode
- `evm_host_bridge.apply_host_op` uses decoder then `_execute_call`
- Optional memory slice → `call_data_hex`; Python reference fallback retained

## Config

- `node_version`: `1.3.49-industrial`

## Tests / gates

- `tests/unit/test_v1349_nested_call_decode.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Nested bytecode / CALL host inside Rust · rewriting `apply_host_op` recursion · CREATE decode · public mainnet
