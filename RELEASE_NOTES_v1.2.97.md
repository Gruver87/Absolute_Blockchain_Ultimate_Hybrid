# Release notes — v1.2.97

**Date:** 2026-07-21  
**Theme:** Lightning/ZK probes, CI bridge gate, audit pack export

## Features / API

- `OPTIONAL_MODULE_PROBES` extended: **lightning**, **zk** (with wasm/plasma)
- `/lightning/stats`, `/zk/info` → `import_error` when module not loaded

## CI / audit export

- GitHub Actions: `bridge_off_audit_gate.py` step (Python 3.12)
- `export_audit_pack.py` includes `bridge_off_audit_gate` output + JSON
- Audit pack docs: `STATE_ROOT_ENCODING_MIGRATION.md`

## Tests

- Extended `test_features_module_probe.py`, `test_export_audit_pack.py`
- Prod smoke profile: explicit `allow_state_root_rewrite=false`, `rate_limit_rpm=120`
- Unit tests aligned with bridge OFF default and prod rate-limiter fail-closed
