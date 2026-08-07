# GitHub repository profile

Apply with:

```powershell
gh repo edit --description "Hybrid Python/Rust L1 node for local mesh and evidence-first R&D — not a public mainnet."
gh repo edit --homepage "https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid#start-in-60-seconds"
# topics (idempotent add):
@(
  "absolute-blockchain","blockchain","blockchain-node","layer1","python","rust","pyo3",
  "p2p","evm","rocksdb","docker","kubernetes","json-rpc","rest-api","devnet",
  "soak-test","cryptography","web3","hybrid-blockchain","blockchain-development"
) | ForEach-Object { gh repo edit --add-topic $_ }
```

Or paste into **Settings → General → About**.

| Field | Value |
|-------|-------|
| **Description** | Hybrid Python/Rust L1 node for local mesh and evidence-first R&D — not a public mainnet. |
| **Website** | https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid#start-in-60-seconds |
| **Social preview** | Upload evergreen `docs/assets/repo-social-preview.png` in **Settings → General → Social preview** |
| **Skimmer card** | [docs/AT_A_GLANCE.md](../docs/AT_A_GLANCE.md) |
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
| **Tag** | `v1.3.1338-deterministic-core` — satoshi state domain + forest-stable LMD-GHOST + QueryPort honesty |
| **Prior** | `v1.3.206` — tip-safety + P2P transport/dispatch |
| **ADR stack** | **0001–0016** (… Observability/Secrets · Feature sprouts/profiles) |
| **Notes** | [CHANGELOG](../CHANGELOG.md) · [DISASTER_RECOVERY](../docs/DISASTER_RECOVERY.md) |
| **Self-check** | `.\scripts\operator_verify.ps1 -SkipNativeBuild` · `.\scripts\check_all.ps1` |
| **CI** | `test.yml`, `docker-prod-image.yml`, `security-audit.yml` (displayed as **Security checks**) |
| **API wave** | 61 |

### Verified locally (Jul 2026)

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

- **Is:** working hybrid L1 R&D stack; local prod-profile 3-node evidence; CI gates; soak-proven ops
- **Is not:** live public mainnet; audited DeFi; investment product
- **Evidence ledger:** `docs/EVIDENCE_MATRIX.md`
- **Banner:** evergreen `docs/assets/repo-banner.svg` (no version chip)
