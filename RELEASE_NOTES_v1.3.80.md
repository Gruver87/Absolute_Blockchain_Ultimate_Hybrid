# Release notes — v1.3.80

## Summary

Inline **simple CREATE** (empty or STOP-only init) via `bridge_state` without Python create hook (Priority 38).

## Changes

- `try_inline_simple_create` for CREATE `0xF0` when init is `[]` or `[STOP]`
- Registers empty runtime in `bridge_state.codes` / `storages`
- Value via fail-closed balances; collision / insufficient → push `0`
- Markers: `native_inline_simple_create`, `native_inline_create_address`
- `node_version`: `1.3.80-industrial`

## Honesty

- CREATE2 and non-trivial init still Python hook
- DB-backed satoshi journal ownership still adapter path
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
```
