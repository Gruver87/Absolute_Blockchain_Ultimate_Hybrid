# Release notes — v1.3.84

## Summary

Inline CREATE/CREATE2 enqueues **`save_account`** into `bridge_state.pending_writeback_ops` (before optional `transfer_value`), matching `evm_plan_create_writeback` order.

## Changes

- Rust `push_pending_writeback_save_account` on successful inline CREATE/CREATE2
- Marker: `native_inline_writeback_create`
- Code hex + empty storage `{}`; balance starts at 0 (value is a separate op)
- `node_version`: `1.3.84-industrial`

## Honesty

- Nested CALL storage still via outer plan; this slice is CREATE account materialization
- Full Rust P2P transport still not claimed
- Not public mainnet; ceremony pin + external audit remain org blockers
- Live mesh: bridge OFF

## Verify

```text
python scripts/verify_industrial_waves.py
```
