# Release notes — v1.3.47

**Date:** 2026-07-25  
**Theme:** Nested CALL effects planner (Priority 19)

## Rust / hybrid

- `evm_plan_nested_call_effects` — pure policy for CALL / CALLCODE / DELEGATECALL / STATICCALL
- Plans nested_read_only, persist storage/value/logs, storage owner, effective value wei
- `execution/evm_adapter.py` `_contract_call_hook` uses planner for frame policy + writeback
- Python reference fallback retained when abs_native symbol missing (prod still prefers native)

## Config

- `node_version`: `1.3.47-industrial`

## Tests / gates

- `tests/unit/test_v1347_nested_call_effects.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Full nested bytecode host inside Rust · Yellow-paper STATICCALL SSTORE mid-frame revert · public mainnet
