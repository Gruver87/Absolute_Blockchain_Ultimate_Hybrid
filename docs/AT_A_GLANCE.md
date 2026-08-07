# At a glance

One-screen card for people who do not read long READMEs. Full detail: [README](../README.md) · proof ledger: [EVIDENCE_MATRIX](EVIDENCE_MATRIX.md).

## What this is

Hybrid **Python + Rust** L1 node with prod-profile Docker mesh, RocksDB, REST/JSON-RPC, `abs_native`, EVM path, port-isolated bridge/RPC/secrets/metrics.

## What it is not

Public audited mainnet · listed ABS token · investment product · bridge ON on live mesh.

## Status

| | |
|---|---|
| Tag | **[v1.3.1339-tip-v2-industrial](https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid/releases/tag/v1.3.1339-tip-v2-industrial)** (audit pin) · prior [v1.3.1338](https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid/releases/tag/v1.3.1338-deterministic-core) |
| Prior industrial | [v1.3.206](../RELEASE_NOTES_v1.3.206.md) tip-safety / P2P |
| ADR stack | **0001–0016** ([docs/adr/](adr/); **0013 unused**) |
| Auditor | [AUDIT_ENGAGEMENT_BRIEF](AUDIT_ENGAGEMENT_BRIEF.md) |
| CI | Ubuntu `test.yml` + docker + security + fuzz (tip-v2 soak gates on `master`) |
| 48h soak (Jul float) | **PASS** (historical / operator-local) |
| 48h soak (tip-v2) | **PASS** Aug 5–7 2026 — `soak_report_tipv2_48h_rerun.json` (fail=0, mesh_warn=0) |
| Phase 3 ops dry-run | **PASS** Aug 7 — [phase3-da25c34](evidence/runs/phase3-da25c34/) |
| Phase 4 audit binder | **READY** Aug 7 — firm engagement pending ([phase4-691329c](evidence/runs/phase4-691329c/)) |
| Self-check | `.\scripts\operator_verify.ps1 -SkipNativeBuild` · `make test-quick` |
| Run | `python main.py` → `:8080` |
| Prod mesh | `778888` bring-up + chain sync · tip v2 `b_satoshi` (ceremony) · `/health/ready` local PASS |

## Proven vs not (honest)

| Proven | Not claimed |
|--------|-------------|
| 3-node prod-profile bring-up + chain sync | Public mainnet |
| Shared ceremony genesis artifact → followers | Always-green `/health/ready` under TLS churn forever |
| 48h soak PASS (Jul float tip, historical) | External L1 / contract audit |
| Failover + signed tx + EVM on mesh | Tip proof / Long-Range / libp2p |
| Forest-stable LMD-GHOST + satoshi storage | Full Rust P2P transport claim |
| **Wave C** tip+apply: tip v2 `b_satoshi` + satoshi apply (fresh mesh) | Public mainnet cutover |
| **tip-v2 48h soak PASS** (Aug 5–7, operator-local) | Listed ABS / investment product |
| **Phase 3–4** ops dry-run PASS + audit binder READY | External firm audit report |
| Bridge **OFF** on live mesh | Live mesh bridge cutover / kitchen-sink FEATURE_* |
| ADR 0010–0016 ports / sprouts in-tree | Kitchen-sink FEATURE_* on `778888` |

## Where code lives

| Path | Role |
|------|------|
| `native/abs_native/` | Rust crypto / Rocks / EVM (`Cargo.toml`) |
| `network/` | P2P TCP + dispatch + adapters |
| `sync/` | Catch-up · fork reconcile · solicit |
| `storage/` | StoragePort · RocksDB adapter |
| `core/` | Blockchain facade · StateService · TxPipeline |
| `api/` | REST/RPC · QueryFacade (ADR 0011) |
| `secret_mgmt/` | SecretManagerPort (ADR 0015) |
| `observability/` | MetricsExporterPort (ADR 0015) |
| `docs/sprouts/` | ADR 0016 profiles (App / Sandbox / Shard / Bridge / EVM) |
| `docs/ARCHITECTURE.md` | System map (mermaid) |
| `docs/DISASTER_RECOVERY.md` | Operator DR runbooks |
| `scripts/` | Ops gates |
| `Makefile` | Linux/macOS shortcuts |

## Next click

- Gaps to mainnet: [MAINNET_GAP_ANALYSIS](MAINNET_GAP_ANALYSIS.md)
- Commands: [COMMANDS_REFERENCE](COMMANDS_REFERENCE.md)
- Contribute: [CONTRIBUTING](../CONTRIBUTING.md)
- GitHub About paste: [REPO_PROFILE](../.github/REPO_PROFILE.md)
