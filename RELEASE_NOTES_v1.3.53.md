# Release notes — v1.3.53

**Date:** 2026-07-25  
**Theme:** Apply isolation metrics, dedicated sync executor, fail-loud backpressure

## Isolation

- Dedicated `ThreadPoolExecutor` (`AbsSyncState`) for `sync_state` — not the default asyncio pool
- `P2PNode._sync_state_async` uses that executor
- Mining: on apply-queue reject → log `apply queue backpressure — skip forge tick`
- Prometheus metrics for queue depth / wait / rejects / P2P import offloads

## Config

- `node_version`: `1.3.53-industrial`
- Existing: `chain_apply_queue_max`, `chain_apply_timeout_sec`

## Tests / gates

- `tests/unit/test_v1353_apply_isolation_metrics.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Public mainnet · tip satoshi root · bridge ON · nested CALL host-in-Rust · claiming “100% global readiness”
