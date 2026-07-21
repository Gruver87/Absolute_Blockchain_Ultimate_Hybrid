# Release notes — v1.2.96

**Date:** 2026-07-21  
**Theme:** Evidence suite bridge gate, WASM/Plasma import probes, release evidence stamp

## Evidence / audit

- `testnet_readiness.ps1` + `prod_evidence_suite.ps1` run `bridge_off_audit_gate`
- Harness check includes `peer_probe_ok`
- `stamp_release_evidence.py` — records `bridge_decision_off` + optional 48h soak stamp
- `external_audit` bridge L1 item now requires `bridge_off_audit_gate` PASS

## API / features

- `/features` → `module_probes` for wasm/plasma
- `/wasm/stats`, `/plasma/stats` → `import_error` when module not loaded

## Tests

- `test_features_module_probe.py`, `test_stamp_release_evidence.py`
