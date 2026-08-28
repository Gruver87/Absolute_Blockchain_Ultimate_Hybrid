# Audits — honest status

**External third-party L1 / smart-contract / penetration audit: not completed.**

This file exists so the repository matches professional open-source practice
(OpenZeppelin-style honesty): a single place that states audit status without
marketing theater.

| Scope | Status | Notes |
|-------|--------|-------|
| In-repo industrial gates (`industrial_gate`, `verify_industrial_waves`) | Active | Code/evidence checks — **not** an external audit |
| Native fuzz (`fuzz-native.yml`) | Active | Coverage-guided / API fuzz — **not** formal verification |
| Security workflow (`security-audit.yml`) | Active | pip-audit + cargo-audit (scoped pyo3 ignores until PR #7) |
| Threat model + scope letter | Ready for engagement | [THREAT_MODEL.md](THREAT_MODEL.md) · [AUDIT_SCOPE.md](AUDIT_SCOPE.md) · [AUDIT_ENGAGEMENT_BRIEF.md](AUDIT_ENGAGEMENT_BRIEF.md) · [AUDIT_PACK_CHECKLIST.md](AUDIT_PACK_CHECKLIST.md) · tag `v1.3.1339-tip-v2-industrial` |
| Independent external audit report | **Pending** | Firm TBD — PDF goes under `audits/<firm>/`; tracker must stay open until then (6/8 automated; 2 firm-owned open) |
| Bug bounty (Immunefi / etc.) | **Not configured** | Disclose via [SECURITY.md](../SECURITY.md) |

## Engagement targets (replace when contracted)

| Field | Value |
|-------|-------|
| Firm | _TBD — do not fake_ |
| Kickoff date | _TBD_ |
| Report URL / path | `audits/<firm>/report.pdf` when received |
| Tracker | `python scripts/external_audit_tracker.py --list` |

When an external report exists, place PDFs under `audits/<firm>/` and link them
from this table. Do **not** claim “audited” in README until that lands.
Do **not** mark tracker items complete with template notes.

Related: [SECURITY.md](../SECURITY.md) · [MAINNET_GAP_ANALYSIS.md](MAINNET_GAP_ANALYSIS.md) · [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md) · [INDUSTRIAL_HARDEN_RUNBOOK.md](INDUSTRIAL_HARDEN_RUNBOOK.md) · [DEPENDABOT_TRIAGE.md](DEPENDABOT_TRIAGE.md)

## Safe Hybrid work while Experimental waits on libp2p 48h

Experimental owns libp2p soak (B1). On **this** pin, prefer:

1. External audit engagement prep ([AUDIT_ENGAGEMENT_BRIEF.md](AUDIT_ENGAGEMENT_BRIEF.md), [AUDIT_PACK_CHECKLIST.md](AUDIT_PACK_CHECKLIST.md), regenerate audit pack)
2. Ops dry-runs (DR / ceremony / bridge-OFF) — no prod secret `-Force` unless cutover day
3. Actions-only Dependabot when CI green (see table above) — **hold** pyo3 / socket2 majors
4. Sprout profiles **off** `778888` (staging / L2 / shard lab compose)

**Operator commands (local, no Experimental port):**

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate_Hybrid
.\scripts\export_audit_pack.ps1
python scripts/external_audit_tracker.py --list
python scripts/industrial_gate.py
```

**Do not:** port libp2p/Long-Range from Experimental · flip refused `feature_*` · claim Experimental TCP+TLS soak `0a7932c4` as Hybrid tip-v2 evidence · start Experimental libp2p 48h from this tree.
