# Release notes — v1.3.56

## Nested CALL/CREATE/LOG host frame

Child CALL frames with host opcodes now run through the Rust full-step runner with a runtime `host_bridge`, instead of falling straight into the Python opcode loop.

### What shipped

- Rust `evm_run_nested_host_frame` (same dispatch as `evm_run_until_halt`, pc=0)
- Python `crypto.native.evm_run_nested_host_frame`
- `EVMAdapter._contract_call_hook` path: pure/bridge eligible → nested pure; else → nested host; else → `execute_bytecode`

### Honesty

- Host opcode **bodies** (CALL/CREATE/LOG/SELFDESTRUCT) still execute via Python `EvmRuntimeBridge.apply_host_op`
- Not “CALL semantics fully in Rust without Python”
- Not a public mainnet claim

### Version

- `node_version`: `1.3.56-industrial`
