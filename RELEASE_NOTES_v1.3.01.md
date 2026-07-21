# Release notes — v1.3.01

**Date:** 2026-07-21  
**Theme:** Soak evidence strict mode, CI audit pack, devnet manifest fail-loud

## Evidence

- `stamp_release_evidence.py` — `--require-soak-hours N` fails closed on missing/failed/short soak
- Soak stamp notes include `soak_git_tag` from report when present
- `restart_soak_prod_mesh.ps1` / `prepare_48h_soak.ps1` — post-soak stamp command hints

## CI

- GitHub Actions: soak-safe `export_audit_pack.py` step (Python 3.12)

## Node boot

- `main.py` — fail-loud warning on devnet `resolve_manifest_path` failure

## Gates

- `industrial_gate` — stamp `--require-soak-hours` + devnet manifest fail-loud checks
