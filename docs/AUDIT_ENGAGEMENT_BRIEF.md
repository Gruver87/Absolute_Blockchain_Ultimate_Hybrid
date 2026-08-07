# Audit engagement brief — Absolute Blockchain Ultimate Hybrid

**One-pager for external security firms.**  
**Product:** Absolute Blockchain Ultimate Hybrid (Python + Rust L1)  
**Repo:** https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid  
**Pin tag:** `v1.3.1339-tip-v2-industrial`  
**Pin commit:** see `git rev-list -n 1 v1.3.1339-tip-v2-industrial`  
**Date:** 2026-08-07  
**Owner:** Gruver87 (Uladzimir Dabranski)

---

## What we are asking you to review

Prod-profile chain **`778888`** (3-node Docker mesh, tip encoding v2 `b_satoshi`, RocksDB, native crypto required, bridge **OFF**).

Full scope letter: [AUDIT_SCOPE.md](AUDIT_SCOPE.md) · threat model: [THREAT_MODEL.md](THREAT_MODEL.md) · status: [AUDITS.md](AUDITS.md).

### In scope (summary)

1. Consensus tip path (import, tip-safety enforce, Path A catch-up, fork reconcile)  
2. State / money (satoshi storage + tip v2 apply / fees / gas / reward)  
3. P2P TLS/mTLS mesh honesty (rate limits, soft-refuse, state_root solicit)  
4. API / RPC (JWT admin, API keys, mempool-only contract deploy in prod)  
5. RocksDB prod path + DR rehearsal scripts  
6. `abs_native` hot-path crypto (`ABS_REQUIRE_NATIVE_CRYPTO`)  
7. Ops gates + packaged evidence under `docs/evidence/runs/`

### Explicitly out of scope

| Item | Why |
|------|-----|
| Bridge ON / L1 lock-mint | Disabled until separate cutover |
| Sharding / L2 / ZK / PQ / Lightning / Plasma / WASM | R&D; FEATURE_* off on prod |
| Full Ethereum client compatibility | EVM subset only |
| Tip proof / Long-Range / libp2p rewrite | Not claimed |
| Public mainnet ops / listing / legal | Organizational |
| `finality_quorum_live=true` marketing | Quorum not live-proven |

---

## Evidence pack (start here)

| Artifact | Path |
|----------|------|
| Static audit zip | `logs/audit_pack_20260807.zip` (operator-local; regenerate: `.\scripts\export_audit_pack.ps1`) |
| Tip-v2 **48h soak PASS** | `docs/evidence/runs/375d14f/` (`passed=true`, fail=0, mesh_warn=0, Aug 5–7 2026) |
| Phase 3 ops dry-run PASS | `docs/evidence/runs/phase3-da25c34/` |
| Phase 4 binder READY | `docs/evidence/runs/phase4-691329c/` |
| Ledger | [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md) |
| Industrial runbook | [INDUSTRIAL_HARDEN_RUNBOOK.md](INDUSTRIAL_HARDEN_RUNBOOK.md) |

**Honesty:** Jul float-tip 48h PASS is separate/historical. Aug 2–4 tip-v2 soak FAIL is historical only (superseded by Aug 5–7 PASS). Do **not** treat `soak_report_tipv2_48h.json` (no `_rerun`) as current claim.

---

## Reproduce locally (Windows)

```powershell
git fetch --tags
git checkout v1.3.1339-tip-v2-industrial
pip install -r requirements.txt
.\scripts\build_native.ps1   # if wheel missing
python scripts/industrial_gate.py --min-soak-hours 48
python scripts/prod_gate.py
python scripts/bridge_off_audit_gate.py
.\scripts\export_audit_pack.ps1
```

Optional live mesh (operator machine): `.\scripts\docker_prod_3node.ps1 -KeepVolumes` then `.\scripts\probe_prod_mesh.ps1 -Quick`.

---

## Deliverables we need from you

1. Written report with severity ratings  
2. Reproduction notes against **this tag**  
3. Explicit statement that tip-v2 + satoshi apply path were in the reviewed build  
4. PDF under agreed path → we place at `audits/<firm>/report.pdf`

---

## What we will **not** claim until your report lands

- “Audited” / “mainnet-ready” / listed ABS  
- Closing tracker items *External penetration test* and *Third-party L1/SC audit*  
- Public testnet DNS/TLS go-live (Phase 5)

Tracker: `python scripts/external_audit_tracker.py --list` (currently **6/8**; 2 firm-owned open).

---

## Contact

GitHub: [@Gruver87](https://github.com/Gruver87) · Security: [SECURITY.md](../SECURITY.md)
