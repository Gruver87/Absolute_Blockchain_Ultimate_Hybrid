# Release notes — v1.3.41

**Date:** 2026-07-21  
**Theme:** EVM host storage snapshot around runner

## Rust / hybrid

- `evm_host_snapshot_storage` / `evm_host_restore_storage` — canonical storage frame snapshots
- `evm_run_until_halt` restores host storage on REVERT / OOG / error (call-frame abort)
- `evm_interpreter.execute_bytecode` takes a host snap and restores on revert / exception
- `EVMAdapter` DELEGATECALL/CALLCODE writeback only when not reverted

## Config

- `node_version`: `1.3.41-industrial`

## Tests / gates

- `tests/unit/test_v1341_evm_host_snapshot.py`
- Industrial gate + post_soak needles for new symbols

## Explicit non-goals

- Full EVM host-in-apply for block mutation · Rocks codecs · P2P rate-limit · public mainnet
