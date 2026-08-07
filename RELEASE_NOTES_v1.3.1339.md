# v1.3.1339 — Tip-v2 industrial (audit pin)

**Tag:** `v1.3.1339-tip-v2-industrial`  
**Purpose:** freeze `master` for external security engagement after industrial Phases 2–4.

## What this tag proves (operator-local + in-repo evidence)

| Claim | Evidence |
|-------|----------|
| Tip-v2 (`b_satoshi`) **48h soak PASS** | `docs/evidence/runs/375d14f/` · `logs/soak_report_tipv2_48h_rerun.json` |
| Phase 3 ops cutover dry-run PASS | `docs/evidence/runs/phase3-da25c34/` |
| Phase 4 audit binder READY | `docs/evidence/runs/phase4-691329c/` · `logs/audit_pack_20260807.zip` |
| Prod adversarial CI soft-skip + soak gate harden | `375d14f` and follow-ups on `master` |

## What this tag does **not** claim

- External firm audit complete  
- Public mainnet / listed ABS  
- Bridge ON  
- Tip proof / Long-Range / libp2p  
- `finality_quorum_live=true`

## Auditor entrypoint

Start at [docs/AUDIT_ENGAGEMENT_BRIEF.md](docs/AUDIT_ENGAGEMENT_BRIEF.md).

## Verify

```powershell
python scripts/industrial_gate.py --min-soak-hours 48
python scripts/bridge_off_audit_gate.py
.\scripts\export_audit_pack.ps1
```

`industrial_gate` may exit 0 with warnings for the two firm-owned audit tracker items and the bridge cutover **example** JSON — expected.
