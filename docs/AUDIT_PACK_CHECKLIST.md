# Audit pack operator checklist (Hybrid pin)

**Purpose:** repeatable, soak-safe steps to regenerate the static audit pack for external firms.  
**Pin:** tag `v1.3.1339-tip-v2-industrial` — **not** the Experimental R&D fork.

Related: [AUDIT_ENGAGEMENT_BRIEF.md](AUDIT_ENGAGEMENT_BRIEF.md) · [AUDITS.md](AUDITS.md) · [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md)

---

## Before you start

- [ ] Work on a clean checkout of **`v1.3.1339-tip-v2-industrial`** (not `main` drift unless intentionally rebasing the pin).
- [ ] Do **not** restart the prod mesh or start a new soak during export — `export_audit_pack` is read-only.
- [ ] Native wheel present or rebuild allowed: `.\scripts\build_native.ps1`.
- [ ] Python deps: `pip install -r requirements.txt`.

```powershell
git fetch --tags
git checkout v1.3.1339-tip-v2-industrial
git rev-list -n 1 v1.3.1339-tip-v2-industrial   # record in engagement email
```

---

## Static gates (required)

Run in order from repo root. All must exit **0** before packaging.

| Step | Command | Pass criterion |
|------|---------|----------------|
| 1 | `python scripts/industrial_gate.py --min-soak-hours 48` | Exit 0; soak evidence needles match [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md) (`375d14f` tip-v2 48h) |
| 2 | `python scripts/prod_gate.py` | Exit 0; prod JSON fail-closed |
| 3 | `python scripts/bridge_off_audit_gate.py` | Exit 0; bridge stays OFF |

Optional (operator machine with live mesh — **not** required for static zip):

```powershell
.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes
.\scripts\probe_prod_mesh.ps1 -Quick
```

---

## Export pack

```powershell
.\scripts\export_audit_pack.ps1
```

Default output: `logs/audit_pack_YYYYMMDD.zip` (see script `--help` / `--out-dir`).

- [ ] Zip created without Docker mesh restart.
- [ ] Manifest inside lists commit SHA matching the checked-out tag.
- [ ] Copy zip to secure share for the firm (do **not** commit zip to git).

JSON-only dry run:

```powershell
.\scripts\export_audit_pack.ps1 -Json
```

---

## What to send the auditor

| Item | Location |
|------|----------|
| Engagement one-pager | [AUDIT_ENGAGEMENT_BRIEF.md](AUDIT_ENGAGEMENT_BRIEF.md) |
| Scope letter | [AUDIT_SCOPE.md](AUDIT_SCOPE.md) |
| Threat model | [THREAT_MODEL.md](THREAT_MODEL.md) |
| Evidence ledger | [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md) |
| Static pack zip | Operator-local `logs/audit_pack_*.zip` |
| Tip-v2 48h soak | `docs/evidence/runs/375d14f/` |

**Honesty:** Jul float-tip 48h PASS is historical. Aug 2–4 tip-v2 soak FAIL is superseded by Aug 5–7 PASS (`375d14f`). Experimental libp2p / Long-Range work lives in [Gruver87/experimental](https://github.com/Gruver87/experimental) — **out of scope** for this pin.

---

## After delivery

- [ ] Update [AUDITS.md](AUDITS.md) when a firm is contracted (no fake “audited” README language until PDF lands).
- [ ] Place report PDF at `audits/<firm>/report.pdf` and link from AUDITS table.
- [ ] Run `python scripts/external_audit_tracker.py --list` and close items only with real evidence URLs.
