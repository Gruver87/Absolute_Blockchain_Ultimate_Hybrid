# Release notes — v1.3.55

**Date:** 2026-07-25  
**Theme:** Nested CALL native bridge surface (BALANCE / EXTCODE* / BLOCKHASH)

## Rust / hybrid

- `evm_bytecode_is_nested_native_eligible` — child may use bridge opcodes; still rejects recursive CALL/CREATE/LOG/SELFDESTRUCT
- `evm_run_nested_pure_frame(..., allow_bridge=True)` keeps `bridge_hooks` / `bridge_state`
- `EVMAdapter._contract_call_hook` prefers native nested path with bridge; Python fallback on host stop

## Config

- `node_version`: `1.3.55-industrial`

## Tests / gates

- `tests/unit/test_v1355_nested_native_bridge.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Recursive CALL/CREATE host inside Rust · rewriting `apply_host_op` · LOG persist in nested Rust · public mainnet
