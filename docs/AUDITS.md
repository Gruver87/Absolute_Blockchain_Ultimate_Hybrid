# Audits — honest status

**External third-party L1 / smart-contract / penetration audit: not completed.**

This file exists so the repository matches professional open-source practice
(OpenZeppelin-style honesty): a single place that states audit status without
marketing theater.

| Scope | Status | Notes |
|-------|--------|-------|
| In-repo industrial gates (`industrial_gate`, `verify_industrial_waves`) | Active | Code/evidence checks — **not** an external audit |
| Native fuzz (`fuzz-native.yml`) | Active | Coverage-guided / API fuzz — **not** formal verification |
| Security workflow (`security-audit.yml`) | Active | Secret scan / dependency hygiene helpers |
| Independent external audit report | **Pending** | Listed as org warning in `industrial_gate` |
| Bug bounty (Immunefi / etc.) | **Not configured** | Disclose via [SECURITY.md](../SECURITY.md) |

When an external report exists, place PDFs under `audits/<firm>/` and link them
from this table. Do **not** claim “audited” in README until that lands.

Related: [SECURITY.md](../SECURITY.md) · [docs/MAINNET_GAP_ANALYSIS.md](MAINNET_GAP_ANALYSIS.md) · [docs/EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md)
