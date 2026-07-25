# Release notes — v1.3.71

## In-Rust inline leaf frame (Priority 37)

### What shipped

- `try_inline_leaf_delegate_call` — eligible DELEGATECALL / value-0 CALLCODE runs inside the parent Rust frame
- Child code from `bridge_state.codes` / bridge `code_copy` (no Rocks in opcode loop)
- Python `contract_call` hook skipped when leaf succeeds
- Rust `evm_bytecode_is_nested_native_eligible` exported (parity with Python gate)

### Honesty

- **Not** a full Rust-owned multi-depth host stack
- Normal CALL / value transfer / CREATE / ineligible children still use Python hooks
- Not a public mainnet claim; bridge OFF on live mesh

### Version

- `node_version`: `1.3.71-industrial`

### Verify

```powershell
python scripts/verify_industrial_waves.py
pytest tests/unit/test_v1371_inline_leaf_frame.py -q
```
