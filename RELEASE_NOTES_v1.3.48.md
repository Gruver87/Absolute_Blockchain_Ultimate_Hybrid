# Release notes — v1.3.48

**Date:** 2026-07-25  
**Theme:** Nested CALL gas planner (Priority 20)

## Rust / hybrid

- `evm_plan_nested_call_gas` — EIP-150 63/64 + 2300 stipend for value-bearing CALL/CALLCODE
- `evm_interpreter._execute_call` uses planner for forwarded `call_gas`
- Python reference fallback retained

## Config

- `node_version`: `1.3.48-industrial`

## Tests / gates

- `tests/unit/test_v1348_nested_call_gas.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Nested bytecode / CALL host inside Rust · porting `apply_host_op` · public mainnet
