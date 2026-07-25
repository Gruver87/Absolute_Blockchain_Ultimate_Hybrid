# Release notes — v1.3.67

## EVM tx writeback journal + Rust storage arena

### What shipped

- `EVMAdapter` buffers nested writeback ops; commits once on top-level success; discards on revert
- Native runner: SLOAD/SSTORE against Rust `HashMap` arena (Priority 34), flush to Python dict on exit

### Honesty

- Not Rocks inside the opcode loop
- Journal still commits via existing Rocks bundle path after top-level success
- Not a public mainnet claim

### Version

- Shipped with `1.3.68-industrial` node tag (same release train)
