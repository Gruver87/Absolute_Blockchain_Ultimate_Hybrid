# Release notes — v1.3.70

## Recursive native frame correctness (arena sync)

### What shipped

- Before nested CALL: flush Rust SLOAD/SSTORE arena → Python storage dict
- After DELEGATECALL/CALLCODE: re-sync arena from merged child storage
- Adapter: `_abs_live_storage` so recursive DELEGATECALL sees parent in-flight SSTOREs
- Nested call results keep `native_nested_pure` / `native_nested_host` flags

### Honesty

- Still re-enters via Python `contract_call` hooks per CALL depth
- **Not** a Rust-owned recursive frame stack / no-FFI interpreter
- Not a public mainnet claim; bridge stays OFF on live mesh

### Version

- `node_version`: `1.3.70-industrial`

### Verify

```powershell
python scripts/verify_industrial_waves.py
pytest tests/unit/test_v1370_recursive_native_frames.py -q
```
