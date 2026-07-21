# Release notes — v1.3.34

**Date:** 2026-07-21  
**Theme:** Rust L1 receipt status + lock verify, optional contract-log bind, atomic debit/refund

## Honesty / fail-closed

- Rust `abs_bridge_bin` v5: verify L1 for `lock`/`bridge` (not only confirm/incoming)
- Rust requires successful receipt `status` (fail-closed on status-less / failed txs)
- Optional `BRIDGE_REQUIRE_L1_EVENT=1` + `BRIDGE_L1_LOCK_CONTRACT`: require a receipt log from that address (`l1_event_bound`); still **not** ABI amount/recipient decode (`l1_event_abi_decoded=false`)
- `confirm_lock` passes lock `to_chain` so BSC/Polygon proofs use the correct RPC
- Outbound debit+burn+lock and refund are atomic (`debit_and_create_bridge_lock` / `refund_pending_bridge_lock`)

## Config

- `node_version`: `1.3.34-industrial`
- `bridge_require_l1_event` / `BRIDGE_REQUIRE_L1_EVENT` (when set with bridge ON in prod, lock contract required)

## Tests / gates

- `tests/unit/test_v1334_honesty.py`
- Industrial gate needles for Rust + Python paths

## Explicit non-goals

- Full escrow ABI decode / audited L1 contracts · public mainnet · BlockBuilder forge wiring
