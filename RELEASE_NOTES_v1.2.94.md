# Release notes — v1.2.94

**Date:** 2026-07-21  
**Theme:** K8s per-pod TLS projected volume, supply/repair fail-loud, harness HTTP test, bridge audit checklist

## Kubernetes

- StatefulSet: **projected** volume merges `abs-p2p-tls` CA + per-ordinal cert-manager secrets (`abs-p2p-tls-node-0..2`)
- `entrypoint.sh`: supports cert-manager `tls.crt`/`tls.key` fallback layout

## API fail-loud

- `/state/supply`, `/state/total-supply`: `supply_error` / `db_supply_error` on DB failures
- `POST /chain/consistency/repair`: `repair_error` when `ensure_state_at_tip` throws
- Sync status: `p2p_sync_error` when `sync_engine.get_status` fails
- Bridge overview: L1 RPC probe errors logged + returned in `l1_rpc.error`

## Evidence

- `docs/EVIDENCE_MATRIX.md`: **Bridge OFF pre-enable audit checklist** (10 controls)

## Tests

- `test_harness_http.py` — GET `/chain/consistency/harness` exposes `peer_probe_ok` + encoding
