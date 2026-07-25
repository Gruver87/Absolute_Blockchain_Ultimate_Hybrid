# Release notes — v1.3.51

**Date:** 2026-07-25  
**Theme:** P2P/sync block import off the asyncio event loop (industrial isolation)

## Isolation

- `P2PNode._import_block_async` — `asyncio.to_thread(import_block)` for announce + sync batch
- `P2PNode._reorg_and_import_async` — offloaded reorg+import for reconcile
- Sync-batch fork `reorg_to_ancestor` also offloaded
- Follower genesis `fast_sync` via `asyncio.to_thread` in `main.py`
- Counter: `ops_errors.import_offload_total`

## Config

- `node_version`: `1.3.51-industrial`

## Tests / gates

- `tests/unit/test_v1351_p2p_import_offload.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Public mainnet · tip satoshi root migration · bridge ON · serial apply queue (v1.3.52) · nested CALL host-in-Rust
