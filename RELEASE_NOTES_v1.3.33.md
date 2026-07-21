# Release notes — v1.3.33

**Date:** 2026-07-21  
**Theme:** Bridge event replay / atomic credit, plasma force, smart-accounts honesty

## Honesty / fail-closed

- Bridge incoming replay key is source-event derived: `(from_chain, event_tx_hash, log_index)` — not claim recipient/amount
- `claim_and_credit_bridge_event` credits + marks replay in one atomic write (SQLite / Rocks)
- Bridge stats / relayer status expose `l1_event_bound=false` (confirmations ≠ escrow log binding)
- Plasma `/plasma/finalize-exit` rejects `force=true` in prod
- Smart Accounts gated by `feature_smart_accounts` (off in prod); `execution_bound` / `persistent` labels

## Config

- `node_version`: `1.3.33-industrial`
- Prod default: `FEATURE_SMART_ACCOUNTS=false`

## Tests / gates

- `tests/unit/test_v1333_honesty.py`
- Extended Rocks bridge credit tests
- Industrial gate needles for the above paths

## Explicit non-goals

- Full L1 escrow event-log decode in Rust bridge · external audit · public mainnet · BlockBuilder forge wiring
