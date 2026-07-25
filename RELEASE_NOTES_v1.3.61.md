# Release notes — v1.3.61

## Native writeback apply (in-memory)

Writeback ops are applied in Rust to an in-memory accounts map. Python DB still commits the resulting rows (and logs).

### What shipped

- `evm_apply_writeback_ops(accounts, ops)` → mutated accounts + log batches
- Adapter: load touched accounts → native apply → `save_account` commit
- Covers `set_storage` / `save_account` / `transfer_value` / `append_logs`

### Honesty

- Not in-process Rocks inside the EVM runner
- Commit still goes through Python `db.save_account` (store locks / hybrid path)
- Not a public mainnet claim

### Version

- `node_version`: `1.3.61-industrial`
