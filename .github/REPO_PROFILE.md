# GitHub repository profile

Apply with:

```powershell
gh repo edit --description "Absolute Blockchain — hybrid Python/Rust L1: prod 3-node mesh, RocksDB, REST/JSON-RPC, EVM, abs_native. 48h soak PASS (Jul 2026). Evidence-first — not a launched public mainnet."
gh repo edit --homepage "https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid#readme"
# topics (idempotent add):
@(
  "absolute-blockchain","blockchain","blockchain-node","layer1","python","rust","pyo3",
  "p2p","evm","rocksdb","docker","kubernetes","json-rpc","rest-api","pos","devnet",
  "tokenomics","industrial","soak-test","cryptography","web3","hybrid-blockchain"
) | ForEach-Object { gh repo edit --add-topic $_ }
```

Or paste into **Settings → General → About**.

| Field | Value |
|-------|-------|
| **Description** | Absolute Blockchain — hybrid Python/Rust L1: prod 3-node mesh, RocksDB, REST/JSON-RPC, EVM, abs_native. 48h soak PASS (Jul 2026). Evidence-first — not a launched public mainnet. |
| **Website** | https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid#30-seconds--see-everything |
| **Social preview** | Upload `docs/assets/repo-banner.svg` (or PNG export) in **Settings → General → Social preview** |
| **Skimmer card** | [docs/AT_A_GLANCE.md](../docs/AT_A_GLANCE.md) |

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
pos
devnet
tokenomics
industrial
soak-test
cryptography
web3
hybrid-blockchain
```

## Branches

| Branch | Role |
|--------|------|
| **`master`** | **Default** — primary development |
| **`main`** | Mirror of `master` (CI sync) |

## Current release

| Field | Value |
|-------|-------|
| **Tag** | `v1.3.159` — height-cap clears fantasy peer.head |
| **Notes** | [RELEASE_NOTES_v1.3.159.md](../RELEASE_NOTES_v1.3.159.md) |
| **Self-check** | `.\scripts\check_all.ps1` |
| **Tests** | 1100+ collected (`pytest tests/ --collect-only`) |
| **CI** | `test.yml`, `docker-prod-image.yml`, `security-audit.yml` |
| **API wave** | 61 |

### Verified locally (Jul 2026)

- Prod mesh probe / failover / signed tx / EVM mempool smoke
- **7h soak PASS** + **48h soak PASS** (2026-07-19→21)
- `industrial_gate --min-soak-hours 48` OK
- Isolated P2P CI (`verify_p2p_ci --mode ci`) OK after signer + mesh_min fix
- Audit pack exporter: `.\scripts\export_audit_pack.ps1`

### Not yet proven (do not claim in About)

- External security audit
- Public VPS testnet URL + DNS/TLS
- Bridge L1 mainnet cutover
- Launched public mainnet / listed ABS token

## Honest positioning (release / About)

- **Is:** working hybrid L1 R&D stack; local prod-profile 3-node evidence; CI gates; soak-proven ops
- **Is not:** live public mainnet; audited DeFi; investment product
- **Evidence ledger:** `docs/EVIDENCE_MATRIX.md`
- **Banner:** `docs/assets/repo-banner.svg`
