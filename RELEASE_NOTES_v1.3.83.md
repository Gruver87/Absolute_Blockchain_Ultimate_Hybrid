# Release notes — v1.3.83

## Summary

Inline value CALL/CREATE enqueues **`transfer_value`** into `bridge_state.pending_writeback_ops` for the adapter satoshi writeback journal (Priority 38).

## Changes

- Rust `push_pending_writeback_transfer` after successful inline value CALL/CREATE
- Markers: `native_inline_writeback_value`, `native_inline_writeback_ops`
- Adapter `_take_bridge_pending_writeback` merges ops into nested writeback / tx journal
- Fail-closed: no op on revert, same-addr CALLCODE, or wei that does not fit `i64`
- `node_version`: `1.3.83-industrial`

## Honesty

- Inline CREATE still does not plan `save_account` via this path (codes map remains ephemeral)
- Sub-satoshi wei (`value_wei < 10**12`) journals as applied no-op in satoshi apply
- Not public mainnet; ceremony pin + external audit remain org blockers
- Live mesh: bridge OFF

## Verify

```text
python scripts/verify_industrial_waves.py
```
