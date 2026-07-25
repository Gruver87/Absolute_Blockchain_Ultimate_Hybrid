# Release notes — v1.3.58

## Native account view decode (nested CALL preload)

Account JSON blobs and contract storage maps decode in Rust for nested CALL preload, so the hot path no longer depends on Python `json.loads` for storage fail-closed checks.

### What shipped

- `account_storage_map_from_raw` — fail-closed `{slot: value}` decode
- `account_view_from_blob` / `account_view_from_json` / `account_view_from_row`
- `RocksEngine.get_account_view(address)`
- `EVMAdapter._account_view` + storage/code preload via native decode

### Honesty

- Persist / CREATE / balance transfer still Python DB write paths
- Not in-process Rocks inside the EVM runner
- Not pure-Rust CALL (hooks + adapter orchestration remain)
- Not a public mainnet claim
- Also fixes CREATE/CALL thin-hook calldata: Rust passes real `bytes` (not `list`) to Python hooks

### Version

- `node_version`: `1.3.58-industrial`
