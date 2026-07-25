# Release notes — v1.3.50

**Date:** 2026-07-25  
**Theme:** Nested pure bytecode frame (Priority 22 first slice)

## Rust / hybrid

- `evm_run_nested_pure_frame` — child CALL frame via pure runner (`host_bridge=None`)
- `evm_bytecode_is_nested_pure_eligible` — skip native path when child has host/bridge ops
- `EVMAdapter._contract_call_hook` fast-path; fall back to Python `execute_bytecode` on host/handoff
- Effects/gas/decode planners from v1.3.47–49 still own policy

## Config

- `node_version`: `1.3.50-industrial`

## Tests / gates

- `tests/unit/test_v1350_nested_pure_frame.py`
- Industrial gate + post_soak needles
- Local check: `python scripts/verify_v1349_local.py` (CALL wave) + v1350 unit test

## Explicit non-goals

- Recursive CALL/CREATE host inside Rust · rewriting `apply_host_op` · BALANCE/EXTCODE*/LOG in nested Rust · public mainnet
