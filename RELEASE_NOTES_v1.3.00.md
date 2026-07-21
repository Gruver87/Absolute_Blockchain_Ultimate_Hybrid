# Release notes — v1.3.00

**Date:** 2026-07-21  
**Theme:** Audit pack encoding snapshot, founder pin fail-loud

## Audit export

- `export_audit_pack.py` writes `gates/state_root_encoding.json` and includes `state_root_encoding` in manifest
- Release notes glob fixed: `RELEASE_NOTES_v*.md` (includes v1.2.99+ and v1.3.x)

## Node boot

- `main.py` `_pin_chain_founder_address`: fail-loud warnings on meta/manifest founder resolve failures
- `.env` load: debug log instead of silent pass

## Gates

- `industrial_gate`: audit pack encoding snapshot + founder pin fail-loud checks

## Not in this release

- Fresh 48h soak stamp — run `.\scripts\restart_soak_prod_mesh.ps1 -Hours 48` when mesh is idle, then `stamp_release_evidence.py`
