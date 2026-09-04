# GitHub repository profile

Apply with:

```powershell
gh repo edit Gruver87/Absolute_Blockchain_Ultimate_Hybrid --description "Absolute Blockchain Ultimate Hybrid — Python+Rust L1, tip-v2 soak PASS, evidence-first industrial pin. External audit pending. Not a public mainnet."
gh repo edit Gruver87/Absolute_Blockchain_Ultimate_Hybrid --homepage "https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid/blob/master/docs/AUDIT_ENGAGEMENT_BRIEF.md"
# topics (idempotent add):
@(
  "absolute-blockchain","blockchain","blockchain-node","layer1","python","rust","pyo3",
  "p2p","evm","rocksdb","docker","kubernetes","json-rpc","rest-api","devnet",
  "soak-test","cryptography","web3","hybrid-blockchain","blockchain-development"
) | ForEach-Object { gh repo edit Gruver87/Absolute_Blockchain_Ultimate_Hybrid --add-topic $_ }
```

Or paste into **Settings → General → About**.

| Field | Value |
|-------|-------|
| **Description** | Absolute Blockchain Ultimate Hybrid — Python+Rust L1, tip-v2 soak PASS, evidence-first industrial pin. External audit pending. Not a public mainnet. |
| **Website** | https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid/blob/master/docs/VISION.md |
| **Social preview** | Upload evergreen `docs/assets/repo-social-preview.png` in **Settings → General · Social preview** |
| **Skimmer card** | [docs/AT_A_GLANCE.md](../docs/AT_A_GLANCE.md) |
| **Vision** | [docs/VISION.md](../docs/VISION.md) |
| **Auditor entry** | [docs/AUDIT_ENGAGEMENT_BRIEF.md](../docs/AUDIT_ENGAGEMENT_BRIEF.md) |
| **Cite** | [CITATION.cff](../CITATION.cff) |
| **Issue chooser** | Bug · Feature · Ops/verify · private vulnerability report · Evidence / SECURITY |

## Topics

```
absolute-blockchain
blockchain
blockchain-node
layer1
python
rust
pyo3
p2p
evm
rocksdb
docker
kubernetes
json-rpc
rest-api
devnet
soak-test
cryptography
web3
hybrid-blockchain
blockchain-development
```

> Cap = 20 topics. Prefer searchable stack terms over maturity labels like `industrial`.

## Branches

| Branch | Role |
|--------|------|
| **`master`** | **Default** — primary development |
| **`main`** | Mirror of `master` (CI sync) |

## Current release

| Field | Value |
|-------|-------|
| **Tag** | `v1.3.1339-tip-v2-industrial` — tip-v2 industrial audit pin (48h soak PASS + Phase 3–4 binder) |
| **Prior** | `v1.3.1338-deterministic-core` — satoshi state domain + forest-stable LMD-GHOST |
| **Prior industrial** | `v1.3.206` — tip-safety + P2P transport/dispatch |
| **ADR stack** | **0001–0016** (0013 unused) · [docs/adr/](../docs/adr/) |
| **Auditor entry** | [AUDIT_ENGAGEMENT_BRIEF](../docs/AUDIT_ENGAGEMENT_BRIEF.md) |
| **Notes** | [CHANGELOG](../CHANGELOG.md) · [DISASTER_RECOVERY](../docs/DISASTER_RECOVERY.md) |
| **R&D sibling** | [`Gruver87/experimental`](https://github.com/Gruver87/experimental) — libp2p 48h PASS (`3c801b87`); LR lab mesh 2h; not the audit pin |
| **Self-check** | `.\scripts\operator_verify.ps1 -SkipNativeBuild` · `.\scripts\check_all.ps1` |
| **CI** | `test.yml`, `docker-prod-image.yml`, `security-audit.yml` (displayed as **Security checks**) |
| **Community health** | **100%** (GitHub community profile) |
| **API wave** | 61 |

### Verified locally (Jul–Aug 2026)

- Prod mesh probe / failover / signed tx / EVM mempool smoke
- **7h soak PASS** + **48h soak PASS** float tip (2026-07-19→21)
- **tip-v2 (`b_satoshi`) 48h soak PASS** (2026-08-05→07) — `docs/evidence/runs/375d14f/`
- **Phase 3 ops dry-run PASS** + **Phase 4 audit binder READY** (2026-08-07)
- `industrial_gate --min-soak-hours 48` OK
- Isolated P2P CI (`verify_p2p_ci --mode ci`) OK after signer + mesh_min fix
- Audit pack exporter: `.\scripts\export_audit_pack.ps1`
- GHOST forest determinism: flake ~37% → 0/30 on hybrid reorg attestation test
- ADR 0015 SecretManager + Prometheus exporter unit coverage

### Not yet proven (do not claim in About)

- External security audit
- Public VPS testnet URL + DNS/TLS
- Bridge L1 mainnet cutover
- Launched public mainnet / listed ABS token
- GPG-signed release tags (annotated tags in use when signing key absent)

## Honest positioning (release / About)

- **Is:** working hybrid L1 R&D stack; local prod-profile 3-node evidence; CI gates; soak-proven ops; audit binder ready
- **Is not:** live public mainnet; audited DeFi; investment product
- **Evidence ledger:** `docs/EVIDENCE_MATRIX.md`
- **Banner:** evergreen `docs/assets/repo-banner.svg` (no version chip)
