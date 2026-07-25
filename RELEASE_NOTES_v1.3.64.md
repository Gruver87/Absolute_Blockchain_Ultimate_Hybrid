# Release notes — v1.3.64

## Rocks batch writeback account preload

Touched accounts for nested writeback are batch-loaded from Rocks before native in-memory apply.

### What shipped

- `RocksEngine.get_account_rows(addresses_json)` → account row map
- `RocksChainStore.load_writeback_accounts` / `HybridDatabase` delegate
- Adapter: Rocks preload → `evm_apply_writeback_ops` → `commit_writeback_bundle`

### Honesty

- Not Rocks ownership inside the EVM opcode loop
- Preload is for the writeback boundary, not per-opcode host state
- Not a public mainnet claim

### Version

- `node_version`: `1.3.64-industrial`
