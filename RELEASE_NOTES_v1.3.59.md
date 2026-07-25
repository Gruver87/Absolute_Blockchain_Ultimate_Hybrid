# Release notes — v1.3.59

## Nested CALL writeback ops (Rust planner)

Nested CALL persist effects are planned in Rust as concrete ops with resolved addresses. Python DB still applies them.

### What shipped

- `evm_plan_nested_call_writeback` → `ops[]`: `set_storage` / `transfer_value` / `append_logs`
- `EVMAdapter._apply_nested_writeback_ops` — apply via existing DB APIs only
- Fail-closed: revert / static / parent read-only → empty `ops`

### Honesty

- Not native Rocks persist
- Not CREATE write path
- Not in-process Rocks inside the EVM runner
- Not a public mainnet claim

### Version

- `node_version`: `1.3.59-industrial`
