# Release notes — v1.3.74

## Priority 38 first slice — value=0 CALL inline

### What shipped

- `try_inline_leaf_value0_call` — eligible **value=0 CALL / STATICCALL** push/pop in Rust
- Callee storage via `bridge_state.storages[addr]` (created/updated on success)
- Python `contract_call` skipped when leaf succeeds
- **Non-zero value** still uses the Python hook (fail-closed: no silent value transfer)

### Honesty

- Not a full multi-depth Rust host stack (children with CALL/CREATE still need hooks)
- Not value-transfer CALL ownership
- Not public mainnet; bridge OFF on live mesh

### Version

- `node_version`: `1.3.74-industrial`

### Verify

```powershell
python scripts/verify_industrial_waves.py
pytest tests/unit/test_v1374_value0_call.py -q
```
