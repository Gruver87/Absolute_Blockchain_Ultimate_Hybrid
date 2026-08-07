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
| Threat model + scope letter | Ready for engagement | [THREAT_MODEL.md](THREAT_MODEL.md) · [AUDIT_SCOPE.md](AUDIT_SCOPE.md) · Phase 2–3 evidence packaged |
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
