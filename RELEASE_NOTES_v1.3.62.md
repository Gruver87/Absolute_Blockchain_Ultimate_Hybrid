# Release notes — v1.3.62

## Store-lock Rocks writeback commit

After native in-memory writeback apply, account rows commit through Rocks under a single store write lock (batch put when available).

### What shipped

- `RocksEngine.commit_account_rows(accounts_json)` — batch put account blobs
- `RocksChainStore.commit_writeback_accounts` / `HybridDatabase` delegate
- Adapter: native apply → `commit_writeback_accounts` (fallback: per-row `save_account`)
- Log batches still persist via Python `_persist_logs`

### Honesty

- Not “Rocks inside the EVM opcode loop”
- Commit still goes through the store lock + state-root accumulator path
- Not a public mainnet claim

### Version

- `node_version`: `1.3.62-industrial`
