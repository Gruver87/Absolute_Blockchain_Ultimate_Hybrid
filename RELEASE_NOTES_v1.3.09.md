# Release notes — v1.3.09

**Date:** 2026-07-21  
**Theme:** Pre-ban strike visibility + loop honesty + k8s embed freeze

## P2P ops honesty

- Every pre-ban strike logs `strike N/M (reason)` — not only the ban line
- `_catch_up_loop` honors `Peer.send` return → `peer_status_send_fail`
- `_maintenance_loop` / `_catch_up_loop` exceptions → warning + `ops_errors.maintenance_loop_fail` / `catch_up_loop_fail`

## Gates / deploy

- `k8s_prod_gate`: ConfigMap embedded JSON must equal `deploy/k8s/node.prod.k8s.json`
- industrial_gate shared keys include `state_root_legacy_cutoff_height`, `rust_bridge_path`, `bridge_auto_confirm_sec`
- `abs_bridge_bin` missing is a **warning** while bridge OFF; **error** if any live prod JSON enables bridge

## Observability

- Alert `AbsoluteP2PAttestationLocalFailBurst` + Grafana panel for attestation local fail

## Verify

```powershell
.\scripts\post_soak_verify.ps1
python scripts/k8s_prod_gate.py
```
