# Release notes — v1.3.43

**Date:** 2026-07-21  
**Theme:** Native P2P rate-limit / strike table

## Rust / hybrid

- `P2PRateLimitTable` — per-peer 1s message window, strike counters, temp bans
- `p2p_rate_limit_tick` / `p2p_rate_limit_is_exempt` / `p2p_strike_should_ban`
- Exempt set matches Python sync/housekeeping wire types
- `network/p2p_node.py` prefers native table; Python dict fallback retained

## Config

- `node_version`: `1.3.43-industrial`

## Tests / gates

- `tests/unit/test_v1343_p2p_rate_limit.py` + `test_p2p_industrial.py`
- Industrial gate + post_soak needles

## Explicit non-goals

- Full EVM host-in-apply · public mainnet · claiming standalone rate table is a full DoS audit
