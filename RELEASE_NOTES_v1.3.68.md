# Release notes — v1.3.68

## Bridge semantic bind + fail-closed debit

### What shipped

- `try_debit_satoshi` — insufficient balance raises (no clamp-to-zero)
- Atomic bridge lock debit uses fail-closed debit under store lock
- Rust `rust_bridge`: when `BRIDGE_L1_LOCK_TOPIC0` + amount/to_addr present, require semantic log bind
- Prod config: `bridge_enabled` requires `bridge_require_l1_event=true`

### Honesty

- Live mesh should keep bridge OFF until audited L1 contracts
- Semantic bind requires configured topic0; otherwise address-level event check remains
- Not a public mainnet claim

### Version

- `node_version`: `1.3.68-industrial`
