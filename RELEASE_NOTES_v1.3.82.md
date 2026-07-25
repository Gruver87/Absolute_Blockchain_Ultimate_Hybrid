# Release notes — v1.3.82

## Summary

Inline CREATE/CREATE2 with **eligible init** that returns runtime bytecode via RETURN (Priority 38).

## Changes

- `run_inline_create_init`: execute leaf-eligible init in Rust; deploy `return_data`
- EIP-170 code size cap (`MAX_INLINE_CREATE_CODE_BYTES = 24576`)
- Markers: `native_inline_create_runtime`, `native_inline_create_runtime_len`
- `node_version`: `1.3.82-industrial`

## Honesty

- Init with CALL/CREATE/LOG/SELFDESTRUCT still Python hook
- DB-backed satoshi journal ownership still adapter path
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
```
