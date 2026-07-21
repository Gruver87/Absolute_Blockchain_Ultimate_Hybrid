# Release notes — v1.2.91

**Date:** 2026-07-21  
**Theme:** P2P ops fail-loud, K8s P2P TLS + Redis wait, verify_p2p fail-closed skips

## P2P fail-loud

- `record_tx_propagation_event`, `connect_peer` task scheduling, and status refresh failures are logged (not silent)
- `get_p2p_security_status().ops_errors` counters exposed via `/status` → `p2p_hardening.ops_errors`

## Kubernetes

- StatefulSet: `wait-redis` initContainer, `abs-p2p-tls` secret mount
- `entrypoint.sh` selects per-pod TLS cert/key by StatefulSet ordinal
- ConfigMap embedded `node.prod.k8s.json` synced with P2P TLS + Redis fields
- `p2p-tls-secret.example.yaml` documents per-replica cert layout
- `k8s_prod_gate` asserts Redis wait, TLS mount, entrypoint wiring

## CI harness

- `verify_p2p_ci` prod-smoke / prod-mesh3 native-wheel skip is **FAIL** unless `VERIFY_P2P_ALLOW_SKIP=1`

## Node startup

- RESTHandler public validator manifest wiring failures logged (not silent)

## Tests

- `test_p2p_ops_errors.py`, `test_verify_p2p_skip_policy.py`
