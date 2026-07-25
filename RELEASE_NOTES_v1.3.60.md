# Release notes — v1.3.60

## CREATE writeback ops (Rust planner)

CREATE/CREATE2 persist effects are planned in Rust as concrete ops. Python DB still applies them through the shared writeback applicator.

### What shipped

- `evm_plan_create_writeback` → `ops[]`: `save_account` + optional `transfer_value`
- Adapter `_contract_create_hook` uses planner + `_apply_nested_writeback_ops`
- Balance starts at 0 on `save_account`; value moves only via `transfer_value` (no double-credit)

### Honesty

- Not native Rocks persist / in-process Rocks in EVM runner
- Address derivation still uses existing native deploy kernels + Python adapter
- Not a public mainnet claim

### Version

- `node_version`: `1.3.60-industrial`
