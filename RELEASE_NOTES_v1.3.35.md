# Release notes — v1.3.35

**Date:** 2026-07-21  
**Theme:** MiniVM/ZK/Lightning/DAO honesty + relayer status not binary smoke

## Honesty / fail-closed

- MiniVM gated by `feature_minivm` (off in prod); mutate APIs blocked in prod; `execution_bound=false` / `r_and_d`
- Lightning: `routing_enabled=false`, direct-channel only; `/lightning/route` returns 501 for multi-hop
- DAO `/pools/dao/vote` forbidden unsigned in prod; dev responses labeled `signature_bound=false`
- ZK: no arithmetic “valid” fallback when module missing; GET `/zk/transaction` disabled (no private keys in query)
- `/status` `bridge_relayer_live=false` until relayer heartbeat; expose `bridge_rust_binary_healthy` + `relayer_observed`

## Config

- `node_version`: `1.3.35-industrial`
- Prod default: `FEATURE_MINIVM=false`

## Tests / gates

- `tests/unit/test_v1335_honesty.py`
- Industrial gate needles for the above paths

## Explicit non-goals

- Full multi-hop LN · signed DAO consensus txs · ZK circuit production · audited L1 escrow ABI decode · public mainnet
