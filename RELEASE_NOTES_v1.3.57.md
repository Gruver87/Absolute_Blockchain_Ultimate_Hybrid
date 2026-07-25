# Release notes — v1.3.57

## Host opcode bodies in Rust (LOG / CALL / CREATE)

Recursive host opcodes no longer require Python `apply_host_op` for the opcode body itself. Gas, stack, memory, and frame decode run in Rust; chain state still comes from thin Python hooks (`contract_call` / `contract_create` / `emit_log` / `selfdestruct`).

### What shipped

- `execute_log_native` — LOG0–LOG4 fully in Rust; segment returns `logs[]`
- `execute_call_native` / `execute_create_native` / `execute_selfdestruct_native`
- `evm_host_context_from_evm` wires `contract_call` / `contract_create` / `selfdestruct` hooks
- Interpreter merges Rust-collected logs into `EVM.logs`

### Honesty

- Not a public mainnet claim
- Nested CALL still needs Python adapter/DB for code+storage (`contract_call` hook)
- CREATE still persists accounts via Python `contract_create` hook
- Runtime `EvmRuntimeBridge.apply_host_op` remains as fallback when hooks are absent

### Version

- `node_version`: `1.3.57-industrial`
