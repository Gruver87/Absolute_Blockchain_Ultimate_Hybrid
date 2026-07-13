# Release Notes — v1.2.51

Date: 2026-07-13

## Bridge cutover becomes “real-deploy” gated (probe/live)

When running `scripts/bridge_l1_preflight.py --probe-l1` (and therefore the cutover gate in probe/live mode), the preflight now checks that:

- `BRIDGE_L1_LOCK_CONTRACT` returns non-empty bytecode via `eth_getCode`
- `BRIDGE_L1_MINT_CONTRACT` returns non-empty bytecode via `eth_getCode`

If either address has empty code (`0x` / `0x0`), the gate **fails closed** — preventing enabling cutover without a real L1 deployment.

## DB migration hardening

Legacy SQLite databases that have an older `accounts(address,balance,nonce)` schema are now automatically migrated to include:

- `accounts.code`
- `accounts.storage`

This prevents failures in account export/state-root logic on old DBs.

