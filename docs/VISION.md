# Absolute Blockchain — Vision & honest scope

**Audience:** grant officers, architects, external auditors, diligent contributors.  
**Not** a retail pitch. **Not** an investment memo.

Canonical pin: [`v1.3.1339-tip-v2-industrial`](https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid/releases/tag/v1.3.1339-tip-v2-industrial)  
R&D sibling: [`Gruver87/experimental`](https://github.com/Gruver87/experimental)

---

## Why Absolute exists

Most public chain READMEs sell a roadmap. Absolute sells **reproducible evidence** for a hybrid L1:

1. **Python orchestrates** (API, P2P policy, node lifecycle).
2. **Rust owns the hot path** (`abs_native`: crypto, satoshi state roots, RocksDB, EVM kernels).
3. **Fail-closed prod profile** — refuse silent fallbacks; bridge **OFF** on live mesh until L1 cutover is audited.
4. **Two repositories on purpose** — industrial freeze stays safe; Experimental absorbs libp2p / Long-Range / depth risk.

If a claim cannot point at a command, lab, soak pack, or gate artifact, it is **not** a claim.

---

## What is proven (Hybrid pin)

| Claim | Status | Where |
|-------|--------|-------|
| Local 3-node prod-profile mesh (chain **778888**) | Proven | Docker compose · probe scripts |
| Tip-v2 satoshi tip + apply | 48h soak **PASS** | [evidence `375d14f`](evidence/runs/375d14f/) |
| Phase 3 ops dry-run | **PASS** | [phase3-da25c34](evidence/runs/phase3-da25c34/) |
| Phase 4 audit binder | **READY** (firm engagement pending) | [phase4-691329c](evidence/runs/phase4-691329c/) · [AUDIT_ENGAGEMENT_BRIEF](AUDIT_ENGAGEMENT_BRIEF.md) |
| Industrial / security CI | Active | `industrial_gate`, `test.yml`, `security-audit.yml` |

One-screen card: [AT_A_GLANCE](AT_A_GLANCE.md) · full ledger: [EVIDENCE_MATRIX](EVIDENCE_MATRIX.md)

---

## What is deliberately not claimed

| Topic | Honest status |
|-------|----------------|
| Public audited mainnet | **No** |
| Listed ABS token / investment product | **No** — in-repo tokenomics model only |
| External firm L1 / penetration audit PDF | **Pending** |
| Bridge ON on live mesh | **OFF** by design |
| rust-libp2p / Long-Range on this pin | **No** — see Experimental |
| Oracles / sharding as prod mesh features | **No** — lab profiles only; flags stay off on `778888` |

Gaps stay listed: [MAINNET_GAP_ANALYSIS](MAINNET_GAP_ANALYSIS.md)

---

## Experimental (sibling) in one paragraph

[`experimental`](https://github.com/Gruver87/experimental) is the R&D sandbox: rust-libp2p (ADR 0019/0020), Long-Range WS labs (ADR 0017), EVM depth / RPC honesty.  
**B1 closed:** Experimental libp2p 48h soak **PASS** [`3c801b87`](https://github.com/Gruver87/experimental/tree/main/docs/evidence/runs/3c801b87) (2026-09-01→03).  
**B2 open:** Long-Range lab 48h (mesh 2h PASS [`lr2hmesh`](https://github.com/Gruver87/experimental/tree/main/docs/evidence/runs/lr2hmesh)). Sequence: [EXECUTION_ORDER](https://github.com/Gruver87/experimental/blob/main/docs/EXECUTION_ORDER.md).  
Lab/Experimental PASS ≠ Hybrid cutover ≠ public mainnet. This pin stays **TCP+TLS**; `feature_libp2p` / `feature_long_range` remain **false**.

---

## How to evaluate Absolute in 15 minutes

1. Read this page + [AT_A_GLANCE](AT_A_GLANCE.md).
2. Open [AUDIT_ENGAGEMENT_BRIEF](AUDIT_ENGAGEMENT_BRIEF.md) (auditor path) or [EVIDENCE_MATRIX](EVIDENCE_MATRIX.md) (proof path).
3. Skim [MAINNET_GAP_ANALYSIS](MAINNET_GAP_ANALYSIS.md) — what we refuse to pretend is done.
4. If reviewing transport / Long-Range: Experimental [EXECUTION_ORDER](https://github.com/Gruver87/experimental/blob/main/docs/EXECUTION_ORDER.md) (B1 closed; B2 open).

---

## Contribution posture

- Prefer issues/PRs with **evidence** (gate JSON, probe output, lab script).
- Do not open Hybrid PRs that port Experimental libp2p / Long-Range onto the freeze.
- Stars and forks are welcome; they are **not** acceptance criteria. Correctness and honesty are.

Author: **Uladzimir Dabranski (D.U.P.)** · GitHub: [Gruver87](https://github.com/Gruver87)

*Last updated: 2026-09-04*
