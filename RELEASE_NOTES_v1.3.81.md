# Release notes — v1.3.81

## Summary

Inline **CREATE2** for empty/STOP-only init (EIP-1014 by default, legacy Absolute seed optional).

## Changes

- Extends `try_inline_simple_create` to opcode `0xF5`
- `create2_eip1014` flag on `bridge_state` / `evm_create2_eip1014` on host context
- Markers: `native_inline_create2`, `native_inline_create2_eip1014`
- `node_version`: `1.3.81-industrial`

## Honesty

- Non-trivial init still Python create hook
- DB-backed satoshi journal ownership still adapter path
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
```
