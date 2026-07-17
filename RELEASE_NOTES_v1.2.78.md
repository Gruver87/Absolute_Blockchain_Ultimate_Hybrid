# Release Notes — v1.2.78

## Industrial audit prep (soak-safe)

Prepare the repository for third-party review **without** touching the live prod mesh or the running 48h soak.

### Added

| Artifact | Purpose |
|----------|---------|
| `scripts/export_audit_pack.py` / `.ps1` | Static pack: industrial/prod gates, audit checklist, evidence docs, soak reports if present, zip + `manifest.json` |
| Tracker UX | `-SyncAutomated`, `-ShowAutomated`, `--evidence-url` / `--evidence-note` |
| `tests/unit/test_export_audit_pack.py` | Manifest shape + evidence fields |

### Fixed

- `prepare_48h_soak.ps1` PowerShell parse error (Unicode em-dash)
- Em-dash in ops `Write-Host` strings (`bridge_cutover_evidence_suite`, `docker_devnet`, `reset_genesis`, `setup_prod_env`)

### Changed

- `industrial_gate.ps1` forwards soak/ceremony/json flags
- Default soak log: `logs/soak_48h_v1.2.77.log`
- Docs: 48h soak is **RUNNING** (started 2026-07-17), **not PASS**

### Honest status

| Item | Status |
|------|--------|
| 7h soak | Proven PASS |
| 48h soak | Running — do not claim PASS until `logs/soak_report_48h.json` has `passed=true` |
| External pen-test / L1 firm audit | Still human organizational items (6/8 automatable) |
| Public mainnet | Not launched |

### Operator commands (safe during soak)

```powershell
.\scripts\export_audit_pack.ps1
.\scripts\external_audit_tracker.ps1 -ShowAutomated
.\scripts\external_audit_tracker.ps1 -SyncAutomated
.\scripts\industrial_gate.ps1
.\scripts\soak_status.ps1
```

Do **not** stop Docker `abs-prod-mesh3` or soak monitors for this release.
