# Release notes — v1.3.52

**Date:** 2026-07-25  
**Theme:** Serial ChainApplyQueue — atomic forge + shared import worker

## Isolation

- `core/chain_apply_queue.py` — single-thread worker; bounded queue (`chain_apply_queue_max`, default 64)
- Mining: `submit_forge_and_apply` = create_block → sign → add_block as one ticket (no import between create and add)
- P2P: import / reorg+import / sync-batch reorg go through the same queue
- Fail-loud backpressure: queue full → reject (no silent drop without counter)

## Config

- `node_version`: `1.3.52-industrial`
- `chain_apply_queue_max` / `CHAIN_APPLY_QUEUE_MAX` (default 64)
- `chain_apply_timeout_sec` / `CHAIN_APPLY_TIMEOUT_SEC` (default 120)

## Tests / gates

- `tests/unit/test_v1352_chain_apply_queue.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Public mainnet · tip satoshi root · bridge ON · Prometheus metrics polish (v1.3.53) · nested CALL host-in-Rust
