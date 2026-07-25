# Release notes — v1.3.63

## Unified writeback bundle (accounts + logs)

Native-applied writeback now commits account rows and EVM log batches in one store-lock path (single Rocks WriteBatch when available).

### What shipped

- `RocksEngine.commit_writeback_bundle(accounts_json, logs_json)`
- `RocksChainStore.commit_writeback_bundle` / `HybridDatabase` delegate
- Adapter: native apply → `commit_writeback_bundle` (accounts + log_batches)
- `commit_account_rows` remains as a thin accounts-only wrapper

### Honesty

- Not Rocks ownership inside the EVM opcode loop
- Bundle still goes through the Python store lock + accumulator upsert for accounts
- Not a public mainnet claim

### Version

- `node_version`: `1.3.63-industrial`
