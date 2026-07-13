# GitHub repository profile

Use in **Settings → General → About** and release tags.

| Field | Value |
|-------|-------|
| **Description** | Hybrid Python/Rust L1 node: P2P mesh devnet, REST/JSON-RPC explorer, ABS tokenomics. Devnet-ready; mainnet-v1 prep (778888) — **not** a launched public mainnet. Evidence: `docs/EVIDENCE_MATRIX.md` |
| **Website** | https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid#readme |
| **Topics** | `blockchain` `python` `rust` `p2p` `rest-api` `json-rpc` `evm` `docker` `kubernetes` `blockchain-node` `devnet` `tokenomics` `rocksdb` `pos` |

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
| **Tag** | `v1.2.77` — P2P sync rate-limit fix (prod mesh catch-up) |
| **Title** | `v1.2.77 — P2P sync rate-limit fix (prod mesh)` |
| **Notes file** | [RELEASE_NOTES_v1.2.77.md](../RELEASE_NOTES_v1.2.77.md) |
| **Tests** | 824 collected (`pytest tests/ --collect-only`) |
| **CI** | `test.yml`, `docker-prod-image.yml`, `security-audit.yml` |
| **API wave** | 61 |

### Verified locally (Jul 13–14, 2026)

- `probe_prod_mesh.ps1` → **OK** (3/3 nodes, aligned height, harness healthy)
- P2P TLS mesh — optional; not required for base prod mesh

### Not yet proven

- 48h soak completion
- External security audit
- Public VPS testnet URL + DNS cutover
- Bridge L1 mainnet cutover (prod mesh: `bridge_enabled=false` by design)

## Recent tags (Jul 2026)

| Tag | Focus |
|-----|-------|
| `v1.2.77` | P2P sync exempt from rate limit |
| `v1.2.76` | Windows P2P TLS generation fix |
| `v1.2.75` | P2P TLS evidence suite |
| `v1.2.74` | Prod mesh resilience + ceremony evidence |
| `v1.2.73` | Bridge cutover evidence + testnet VPS ops |
| `v1.2.72` | VPS mesh3 bootstrap + DNS cutover probe |
| `v1.2.71` | Public testnet 3-node seed |

## Honest positioning (for release body)

- **Is:** working R&D L1 stack; 3-node prod-profile mesh evidence; RocksDB + CI gates; health watch / DR / resilience scripts
- **Is not:** live public mainnet; **external audit not completed**; audited DeFi; listed ABS token
- **Ops gaps:** 48h soak, public testnet VPS, prod P2P TLS (optional path), bridge L1 cutover — see `docs/EVIDENCE_MATRIX.md`
- **Bridge on prod:** off by default until L1 cutover (`BRIDGE_ENABLED=false`, see `docs/BRIDGE_L1_MAINNET.md`)
