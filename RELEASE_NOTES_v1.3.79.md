# Release notes — v1.3.79

## Summary

Inline **CALLCODE with value** via fail-closed `bridge_state.balances` (Priority 38 follow-on).

## Changes

- `try_inline_leaf_delegate_call` accepts CALLCODE `value > 0` when balances are present
- Same-address credit (current account) — net no-op after insufficient-balance check
- Observability flag: `native_inline_callcode_value`
- `node_version`: `1.3.79-industrial`

## Honesty

- CREATE / CREATE2 frames still via Python hook
- DB-backed satoshi journal ownership still via adapter path
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
```
