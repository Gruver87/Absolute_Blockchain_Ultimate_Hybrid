# Industrial harden runbook (Phases 2–5)

Operator checklist for the no-new-features industrial program.  
Do **not** enable sharding / bridge / FEATURE_* on `778888`.

## Phase 2 — Tip-v2 proof

```powershell
.\scripts\docker_prod_3node.ps1 -NoCloneDb   # wipe required across encoding cutovers
$env:PYTHONPATH = (Get-Location).Path
python scripts/verify_p2p_ci.py --mode ready-check `
  --url1 http://127.0.0.1:18180 --url2 http://127.0.0.1:18181 --url3 http://127.0.0.1:18182
.\scripts\probe_prod_mesh.ps1 -Quick
.\scripts\prod_mesh_failover.ps1
python scripts/prod_signed_tx_smoke.py
python scripts/prod_evm_smoke.py
.\scripts\soak_monitor.ps1 -ProdMesh -Hours 48 -IntervalSec 300
python scripts/package_mesh_evidence.py --out docs/evidence/runs/<sha> `
  --probe-log logs/prod_mesh_probe.json --soak-report logs/soak_report.json
```

Stop: soak `passed=true`, matching tip roots, encoding v2 active on all three nodes.

**Status (2026-08-07):** Phase 2 tip-v2 **48h PASS** — `logs/soak_report_tipv2_48h_rerun.json` + evidence `docs/evidence/runs/375d14f/` (`passed=true`, fail=0, mesh_warn=0, 48.00h). Prior Aug 2–4 FAIL remains historical only.

## Phase 3 — Ops cutover dry-run

```powershell
python scripts/bridge_off_audit_gate.py
.\scripts\ceremony_evidence_suite.ps1   # if present; else genesis_ceremony_keygen dry docs
# pin_ceremony_hash.ps1 — dry-run only until real keys
.\scripts\rotate_prod_secrets.ps1   # dry-run: prints plan, exits 0; use -Force only on cutover host
.\scripts\dr_restore_rehearsal.ps1 -DockerMesh1
```

Stop: bridge OFF gate PASS; DR rehearsal PASS; ceremony/secrets steps recorded (secrets gitignored).  
Session note: `rotate_prod_secrets.ps1` without `-Force` is the documented dry-run (no mutation).

**Status (2026-08-07):** Phase 3 **PASS** (dry-run) — evidence `docs/evidence/runs/phase3-da25c34/`:
- bridge_off_audit_gate PASS  
- ceremony_evidence_suite PASS (hash `e7d0c1ed…` matches `.env` pin)  
- `rotate_prod_secrets.ps1` dry-run PASS (**no** `-Force`)  
- `dr_restore_rehearsal.ps1 -DockerMesh1` PASS (tip=4643)  
- external audit tracker 6/8 (2 firm-owned remaining)

## Phase 4 — Audit binder

- [THREAT_MODEL.md](THREAT_MODEL.md)  
- [AUDIT_SCOPE.md](AUDIT_SCOPE.md)  
- [AUDITS.md](AUDITS.md) + PDF under `audits/<firm>/` when available  
- [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md) tip-v2 soak row  

**Status (2026-08-07):** Phase 4 binder **READY for firm engagement** — evidence `docs/evidence/runs/phase4-691329c/`:
- threat model + audit scope refreshed  
- `industrial_gate.py --min-soak-hours 48` PASS (tip-v2 report)  
- `export_audit_pack` → `logs/audit_pack_20260807.zip`  
- tracker **6/8** (2 firm-owned: pen-test + L1/SC audit)  
- **Not** “audited” until PDF under `audits/<firm>/`  
- Engagement brief: [AUDIT_ENGAGEMENT_BRIEF.md](AUDIT_ENGAGEMENT_BRIEF.md) · pin tag `v1.3.1339-tip-v2-industrial`  

## Phase 5 — Public surface (after 1–4)

See [PUBLIC_TESTNET.md](PUBLIC_TESTNET.md) + [MAINNET_CUTOVER.md](MAINNET_CUTOVER.md).  
Do not claim mainnet-ready until external tracker complete + public TLS evidence.

## Non-goals

Sharding on prod tip · `finality_quorum_live` marketing · bridge enablement · new FEATURE_*  
libp2p / Long-Range on this freeze (R&D: [Gruver87/experimental](https://github.com/Gruver87/experimental); `feature_libp2p` / `feature_long_range` hard-off on `778888`)  
