# Release notes — v1.2.90

**Date:** 2026-07-21  
**Theme:** Honest `/status`, prod mesh Redis validate, fail-loud WS/backup

## `/status` honesty

- `core_real` reflects live capability (bridge off ⇒ relayer not live)
- `middleware.rate_limit_backend` + `p2p_hardening` TLS truth
- `monolith_summary.rate_limit` snapshot

## Config / K8s

- Prod mesh (`mesh_min_peers_before_mine >= 1`) requires `REDIS_URL` + `REDIS_RATE_LIMIT`
- K8s: Redis health probes, node TLS + Redis in `node.prod.k8s.json`, stricter `k8s_prod_gate`

## Fail-loud

- ChainStorage JSON backup failures logged (not silent)
- WebSocket send/handler errors counted + logged
- Consensus casper/beacon `add_block` errors logged
- Bridge oracle verify warnings logged

## Tests

- `test_status_honesty.py`, `test_websocket_fail_loud.py`
