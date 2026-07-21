# GitHub repository profile

Copy into **Settings → General → About** (or apply via `gh repo edit`).

| Field | Value |
|-------|-------|
| **Description** | Hybrid Python/Rust L1: prod 3-node mesh, RocksDB, REST/JSON-RPC, EVM path. **48h soak PASS** (Jul 2026). Devnet-ready; mainnet-v1 prep (778888) — **not** a launched public mainnet. |
| **Website** | https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid#readme |
| **Topics** | see list below |

## Topics (paste in GitHub UI)

```
blockchain
python
rust
pyo3
p2p
rest-api
json-rpc
evm
docker
kubernetes
rocksdb
devnet
tokenomics
blockchain-node
pos
industrial
soak-test
```

## Branches

| Branch | Role |
|--------|------|
| **`master`** | **Default** — primary development |
| **`main`** | Mirror of `master` (CI sync) |

## Current release

| Field | Value |
|-------|-------|
| **Tag** | `v1.2.95` — bridge OFF audit gate, K8s TLS merge job |
| **Notes** | [RELEASE_NOTES_v1.2.95.md](../RELEASE_NOTES_v1.2.95.md) |
| **Prior** | [v1.2.87](../RELEASE_NOTES_v1.2.87.md) pre-audit fail-closed + P2P TLS |
| **Tests** | 824+ collected (`pytest tests/ --collect-only`) |
| **CI** | `test.yml`, `docker-prod-image.yml`, `security-audit.yml` |
| **API wave** | 61 |

### Verified locally (Jul 2026)

- Prod mesh probe / failover / signed tx / EVM mempool smoke
- **7h soak PASS** + **48h soak PASS** (2026-07-19→21)
- `industrial_gate --min-soak-hours 48` OK
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
