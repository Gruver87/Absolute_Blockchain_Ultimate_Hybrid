# Release notes — v1.2.92

**Date:** 2026-07-21  
**Theme:** Mining fail-loud, state_root encoding scaffold, K8s cert-manager example

## Mining loop fail-loud

- Cross-shard, PBS auction, MEV scan, light client, epoch pool unlock — logged (not silent)
- DB close on shutdown logged
- Founder wallet template read failures logged

## State-root encoding scaffold

- `runtime/state_root_encoding.py`: v1 `float_b_round12` (active), v2 `satoshi_b` (blocked scaffold)
- `/status` and `get_state_root_policy()` expose honest `encoding` snapshot
- v2 request without migration stays inactive (fail-closed)

## API

- Oracle registry sync failures logged
- `/validators/registry` merge failures return `merge_error` (honest fallback)

## Kubernetes

- `cert-manager-p2p.example.yaml` — optional per-pod mTLS Certificate wiring

## Tests

- `test_state_root_encoding.py`
- `test_status_honesty` checks `state_root_policy.encoding`
