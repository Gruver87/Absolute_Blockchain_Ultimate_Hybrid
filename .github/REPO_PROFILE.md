# GitHub repository profile

Use in **Settings → General → About** and release tags.

| Field | Value |
|-------|-------|
| **Description** | Hybrid Python/Rust L1 node: P2P mesh devnet, REST/JSON-RPC explorer, PoS-style consensus, ABS tokenomics model, Rust bridge path. Devnet-ready; mainnet-v1 prep (chain 778888) — not a launched public mainnet. |
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

## Current release

| Field | Value |
|-------|-------|
| **Tag** | `v1.2.1` |
| **Title** | `v1.2.1 — Devnet ops & mainnet-v1 clarity` |
| **Notes file** | [RELEASE_NOTES_v1.2.1.md](../RELEASE_NOTES_v1.2.1.md) |
| **Tests** | 698 passed, 1 skipped (`pytest tests/ -q`) |
| **API wave** | 61 |

## Previous tags (historical)

- `v1.2.0-industrial` — Waves 37–63, industrial profile
- `v61.x` — API wave milestones
- `v1.0-educational` — early educational profile

## Honest positioning (for release body)

- **Is:** production-hardened R&D node, multi-node Docker devnet, prod fail-closed config gates
- **Is not:** live public mainnet, audited DeFi, listed ABS token, investment product
- **Bridge on prod:** off by default until L1 cutover (`BRIDGE_ENABLED=false`, see `docs/BRIDGE_L1_MAINNET.md`)
