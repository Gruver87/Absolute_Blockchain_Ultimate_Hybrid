# Release notes — v1.2.95

**Date:** 2026-07-21  
**Theme:** bridge_off_audit_gate, K8s TLS merge job, consensus import fail-loud

## Bridge OFF automation

- `scripts/bridge_off_audit_gate.py` — automated 10-control checklist from EVIDENCE_MATRIX
- Wired into `industrial_gate`; writes `data/bridge_off_audit_gate.json`

## Kubernetes

- `deploy/k8s/merge_p2p_tls_secrets.sh` — merge per-pod cert-manager secrets → `abs-p2p-tls`
- `deploy/k8s/p2p-tls-merge-job.example.yaml` — optional Job + RBAC

## API

- `/consensus/casper` and `/consensus/beacon` import probes return `import_error` + debug log

## Tests

- `test_bridge_off_audit_gate.py`
