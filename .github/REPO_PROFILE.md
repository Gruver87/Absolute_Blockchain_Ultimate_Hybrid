# GitHub repository profile

Use in **Settings → General → About** and release tags.

| Field | Value |
|-------|-------|
| **Description** | Hybrid Python/Rust L1: 3-node prod-profile mesh (778888 prep), RocksDB, CI gates. Working R&D stack — **not** launched mainnet; external audit not completed. Evidence: `docs/EVIDENCE_MATRIX.md` |
| **Website** | https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid#readme |
| **Topics** | `blockchain` `python` `rust` `p2p` `rest-api` `json-rpc` `evm` `docker` `kubernetes` `blockchain-node` `devnet` `tokenomics` |

## Topics (one per line in GitHub UI)

```
blockchain
python
rust
p2p
rest-api
json-rpc
evm
web-explorer
docker
kubernetes
blockchain-node
devnet
tokenomics
pos
sqlite
rocksdb
```

## Branches

| Branch | Role |
|--------|------|
| **`master`** | **Default** — primary development |
| **`main`** | Mirror of `master` (auto-sync via `.github/workflows/sync-main-from-master.yml`) |

Local push: `.\scripts\push_origin.ps1` or `git push origin master`.

## Current release

| Field | Value |
|-------|-------|
| **Tag** | `v1.2.14` (code may be ahead; see CHANGELOG) |
| **Title** | `v1.2.14 — CI badges, architecture, security audit` |
| **Notes file** | [CHANGELOG.md](../CHANGELOG.md) |
| **Tests** | 703 collected (`pytest tests/ --collect-only`) |
| **CI** | `test.yml`, `docker-prod-image.yml`, `security-audit.yml` |
| **API wave** | 61 |

## Previous tags (historical)

- `v1.2.4` — RocksDB tuning & DR rehearsal
- `v1.2.3` — RocksDB backup & restore
- `v1.2.2` — Docker GHCR + fast mesh ops
- `v1.2.1` — Devnet ops & mainnet-v1 clarity
- `v1.2.0-industrial` — Waves 37–63, industrial profile
- `v1.0-educational` — early educational profile

## Honest positioning (for release body)

- **Is:** working R&D L1 stack; 3-node prod-profile mesh evidence; RocksDB + CI gates; health watch / DR scripts
- **Is not:** live public mainnet; **external audit not completed**; audited DeFi; listed ABS token
- **Ops gaps:** failover under load, default prod signed-tx path, prod EVM RPC e2e, 24–48h soak completion — see `docs/EVIDENCE_MATRIX.md`
- **Bridge on prod:** off by default until L1 cutover (`BRIDGE_ENABLED=false`, see `docs/BRIDGE_L1_MAINNET.md`)
