# Absolute Blockchain Ultimate

> **Educational Python blockchain node** — L1 core, REST/RPC, web explorer, PoS-style consensus, ABS tokenomics model.

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Educational%20Only-orange)]()
[![API Wave](https://img.shields.io/badge/API%20Wave-61-blue)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Unit%20Tests-246%20passed-brightgreen)](tests/unit/)
[![Audit](https://img.shields.io/badge/Full%20Audit-passing-brightgreen)](scripts/full_audit.py)
[![Release](https://img.shields.io/badge/Release-v1.2.0--industrial-blue)](https://github.com/Gruver87/absolute-blockchain-ultimate/releases)

**Repo:** [github.com/Gruver87/absolute-blockchain-ultimate](https://github.com/Gruver87/absolute-blockchain-ultimate)

| Field | Value |
|-------|-------|
| **Version** | `1.2.0-industrial` |
| **API Wave** | `61` → check `GET /status` → `api_wave` + `core_real` |
| **Entry point** | `python main.py` |
| **Storage** | SQLite `data/blockchain.db` |
| **Chain ID (dev)** | `77777` |

| Docs | Link |
|------|------|
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| Honest command reference | [docs/ALL_COMMANDS.txt](docs/ALL_COMMANDS.txt) |
| Roadmap | [docs/INDUSTRIAL_ROADMAP.md](docs/INDUSTRIAL_ROADMAP.md) |
| Disclaimer | [DISCLAIMER.md](DISCLAIMER.md) |

---

## ⚠️ Disclaimer (read first)

| | |
|---|---|
| **What it is** | Learning / R&D codebase, portfolio demo, community fork base |
| **What it is NOT** | Production mainnet, audited DeFi, listed token, investment product |
| **ABS token** | In-repo **simulation** (221M cap model) — **not** a tradable asset |
| **Security** | No formal audit; do **not** use for real funds |

---

## Snapshot (for reviewers & investors)

**Absolute Blockchain Ultimate** is a single-process educational L1 node: real SQLite persistence, deterministic `state_root`, multi-node P2P sync, a full REST/RPC surface, and a browser explorer — designed as a portfolio-grade demo and research base, not as a production mainnet.

| Area | Level | What is verified in-repo |
|------|-------|--------------------------|
| **L1 core** | 🟢 Production-quality demo | Blocks, balances, 2% burn, genesis, ECDSA txs, auto-mining ~12–15s |
| **REST API** | 🟢 | **283+** route handlers, OpenAPI `/docs`, `api_wave=61` |
| **Web Explorer** | 🟢 | SPA at `:8080` — **32** functional tabs |
| **P2P networking** | 🟢 Verified | 2 / 3 / 5-node Docker meshes; strict `state_root`, topology, and rejoin APIs |
| **TX propagation** | 🟢 | Signed gossip + mempool pull + `/tx/trace/{hash}` |
| **Multi-validator devnet** | 🟢 | 5 validators, proposer rotation, 3 miners + 2 attesters |
| **State consistency** | 🟢 | Cross-node harness + auto-repair (`/chain/consistency/*`) |
| **Fork & slashing CI** | 🟢 | `/testnet/fork-status`, double-vote detection |
| **JSON-RPC** | 🟢 | `eth_*` subset (MetaMask-style) on `:8545` |
| **Tokenomics model** | 🟢 | 221M ABS cap, founder D.U.P. 17.4% — enforced in code |
| **EVM / L2 / Bridge** | 🟡 Educational | Working demos with SQLite persistence; not full Ethereum parity |
| **Production mainnet** | 🔴 Out of scope | By design — see [DISCLAIMER.md](DISCLAIMER.md) |

**Quality gate (Jun 2026):** `246 passed, 1 skipped` · **`python scripts/full_audit.py --live --p2p`** → 12/12 sections OK

---

## What you get out of the box

| Capability | Status | How to try |
|------------|--------|------------|
| Solo node + Explorer | ✅ | `python main.py` → http://localhost:8080 |
| Two-node local devnet | ✅ | `.\scripts\start_two_nodes.ps1` |
| Docker 2-node mesh | ✅ | `.\scripts\docker_devnet.ps1` |
| Docker 3-node testnet (Wave 52) | ✅ | `.\scripts\docker_devnet_3node.ps1` |
| Docker 5-validator devnet (Wave 55) | ✅ | `.\scripts\docker_devnet_5validator.ps1` |
| P2P sync verification | ✅ | `python scripts/verify_p2p_ci.py --mode devnet3` |
| Full project audit (one command) | ✅ | `python scripts/full_audit.py --live --p2p` |
| Unit + integration tests | ✅ | `pytest tests/ -q` |
| Cross-chain bridge (sim / rust) | ✅ Demo | Explorer → Cross-Chain tab |
| NFT marketplace | ✅ Demo | Persisted in SQLite |
| Lightning / Plasma / WASM / Will | ✅ Demo | `GET /l2/status` |
| Oracles (prices + weather) | ✅ Demo | `GET /oracles/prices` |
| Post-quantum crypto demos | ✅ Educational | SPHINCS+, Kyber, Dilithium |

---

## Core L1 + P2P (Waves 47–63)

| Wave | Feature | Key endpoints |
|------|---------|---------------|
| **47** | TX receipts + chain metrics | `GET /chain/metrics`, `GET /tx/receipt/{hash}` |
| **48** | Address tx index | `GET /address/{addr}/activity`, `GET /address/{addr}/txs` |
| **49** | Block proposer audit | `GET /chain/proposers/stats`, `GET /chain/proposer/{addr}` |
| **50** | Strict `state_root` on P2P | `GET /chain/state-root/status` |
| **52** | **3-node testnet** | `GET /testnet/mesh`, `docker_devnet_3node.ps1` |
| **53** | **Fork / slashing CI** | `GET /testnet/fork-status`, `GET /slashing/events`, `--mode ci3` |
| **54** | **State consistency harness** | `GET /chain/consistency/harness`, `POST /chain/consistency/repair` |
| **58** | **Fork CI** | `POST /testnet/fork-exercise`, `--mode ci-fork` partition recovery |
| **59** | **Bridge relayer e2e** | `POST /bridge2/transfer` → RustBridge, L1 queue, `--mode ci-bridge` |
| **60** | **Mock L1 + relayer CI** | `GET /testnet/bridge-relayer-proof`, `--mode ci-bridge-relayer` |
| **61** | **Network hygiene + peer rejoin** | `GET /p2p/topology`, `POST /p2p/reconnect`, stable advertised peer ports |
| **62** | **Live Docker recovery gate** | `--mode devnet3-recovery`, `docker_devnet_3node.ps1 -Recovery`, restart/rejoin `state_root` convergence |
| **63** | **Admin repair endpoint lockdown** | `JWT_ENFORCE_ADMIN=true`, protected sync/reconnect/repair/fork drill POSTs |
| **57** | **Real core** | deterministic proposer, finality quorum, reorg guard, mempool MEV |
| **56** | **Multi-node proof** | `GET /testnet/multi-node-proof`, `POST /testnet/reorg-exercise`, 3-validator rotation |
| **55** | **5-validator devnet** | `GET /testnet/validators`, `docker_devnet_5validator.ps1` |

```powershell
(Invoke-RestMethod http://localhost:8080/status -UseBasicParsing).api_wave   # → 61
Invoke-RestMethod http://localhost:8080/p2p/topology -UseBasicParsing
Invoke-RestMethod http://localhost:8080/testnet/validators -UseBasicParsing
Invoke-RestMethod http://localhost:8080/chain/consistency/harness -UseBasicParsing

# 5-validator devnet (Wave 55):
.\scripts\docker_devnet_5validator.ps1
python scripts/verify_p2p_ci.py --mode devnet5

# 3-node testnet (Wave 61 verified):
.\scripts\docker_devnet_3node.ps1
python scripts/verify_p2p_ci.py --mode devnet3 --wait 300

# Industrial recovery gate (Wave 62):
.\scripts\docker_devnet_3node.ps1 -Recovery
python scripts/verify_p2p_ci.py --mode devnet3-recovery --wait 300

# Adversarial / bridge CI (no Docker):
python scripts/verify_p2p_ci.py --mode ci3
python scripts/verify_p2p_ci.py --mode ci-fork
python scripts/verify_p2p_ci.py --mode ci-bridge
python scripts/verify_p2p_ci.py --mode ci-bridge-relayer
# Send tx (node1 wallet auto_sign), then trace:
Invoke-RestMethod http://localhost:8080/tx/send -Method POST -ContentType application/json -Body '{"auto_sign":true,"to":"0x2222222222222222222222222222222222222222","value":0.01}'
Invoke-RestMethod http://localhost:8081/mempool -UseBasicParsing   # same tx on node2
Invoke-RestMethod http://localhost:8080/tx/trace/{hash} -UseBasicParsing
```

Full wave history (37–63): [CHANGELOG.md](CHANGELOG.md)

---

## Tokenomics (in-repo model)

| Param | Value |
|-------|-------|
| Symbol | **ABS** |
| Max supply | **221 000 000** |
| Founder | **Uladzimir Dabranski** (D.U.P.) — **17.4%** = 38 454 000 ABS |
| Ecosystem / Treasury | 10% + 10% (DAO unlock rules in code) |
| Staking pool | 12.6% (epoch release) |
| Mining emission | 50% until cap |

Config: `runtime/tokenomics.py` · API: `GET /tokenomics`

---

## Quick start

### Requirements

- Python **3.10+** (3.11–3.13 tested)
- Windows / Linux / macOS
- Docker Desktop — optional, for `docker_devnet.ps1`

### Install

```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
pip install -r requirements.txt
cp .env.example .env
cp wallet.example.json data/wallet.json
```

Secrets (`BRIDGE_ORACLE_SECRET`, `TELEGRAM_BOT_TOKEN`, RPC keys) — **only in `.env`**, never commit.

### Run

```bash
python main.py
```

| Service | URL |
|---------|-----|
| Explorer + REST | http://localhost:8080 |
| L2 dashboard | http://localhost:8080/l2/status |
| JSON-RPC | http://localhost:8545 |
| WebSocket | ws://localhost:8766 |
| P2P | `:5000` |

### Two nodes (P2P)

```powershell
.\scripts\stop_node.ps1
.\scripts\start_two_nodes.ps1 -RustBridge -Fresh    # :8080 + :8081

# or Docker:
.\scripts\docker_devnet.ps1 -RustBridge
```

Expected when healthy:

```
OK: peers n1=1 n2=1 heights X / X state_consistent=True state_roots_match=True
api_wave=61
```

### Full audit (recommended before release)

Single script — syntax, tokenomics, Waves 52–61, secrets scan, mega/final audit, pytest, live API, P2P mesh:

```powershell
python scripts/full_audit.py --live --p2p
# Report: data/full_audit_report.json
```

### Verify

```powershell
pytest tests/ -q
pytest tests/unit/ -q                              # 246 passed, 1 skipped
python scripts/verify_p2p_ci.py --mode devnet3 --wait 300    # 3-node mesh
python scripts/verify_p2p_ci.py --mode devnet3-recovery --wait 300    # node restart/rejoin
python scripts/verify_p2p_ci.py --mode devnet5    # 5-validator mesh
python scripts/verify_p2p_ci.py --mode ci-bridge-relayer
curl.exe http://localhost:8080/health/live
curl.exe http://localhost:8080/status
curl.exe http://localhost:8080/p2p/topology
curl.exe http://localhost:8080/testnet/validators
curl.exe http://localhost:8080/chain/consistency/harness
```

---

## Architecture (short)

```
main.py → NodeOrchestrator
├── core/blockchain.py      # L1 blocks, txs, state_root
├── storage/database.py     # SQLite (L1 + L2 tables)
├── api/http.py             # REST + explorer backend
├── consensus/              # PoS adapter, slashing, finality
├── execution/              # VM, state engine, EVM adapter
├── features/               # L2, NFT, oracles, reorg, MEV…
├── network/p2p_node.py     # TCP gossip, sync, state_root wire
└── web/explorer/           # Browser UI
```

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · Honest feature list: [docs/ALL_COMMANDS.txt](docs/ALL_COMMANDS.txt) Part 0

---

## API cheat sheet

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/status` | `api_wave`, peers, bridge, flags |
| GET | `/sync/status` | heights, `state_consistent`, policy |
| GET | `/chain/metrics` | block time, tx/receipt/proposer counts |
| GET | `/chain/state-root/status` | roots vs peers, mismatches |
| GET | `/address/{addr}/activity` | balance, blocks_proposed, tx counts |
| GET | `/chain/proposer/{addr}` | proposer audit detail |
| GET | `/l2/status` | Lightning, Plasma, NFT, WASM… |
| GET | `/features` | modules + persisted flags |
| GET | `/tokenomics` | supply model |
| POST | `/bridge/dev-confirm-pending` | dev only |

Full list: `api/http.py`, `/docs`, `docs/ALL_COMMANDS.txt`

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Connection closed right after Docker up | Wait for `/status` or run `docker_devnet.ps1` |
| `api_wave` &lt; 60 in Docker | `docker compose -f docker-compose.devnet-rust.yml build --no-cache node1` + recreate |
| Ports busy | `.\scripts\stop_node.ps1` |
| Docker `:8080/:8082` shows `node-1` or `501` | A local `python main.py` is intercepting host ports; stop it before Docker devnet |
| Docker not running | Start Docker Desktop |

---

## Contributing

⭐ Star · 🍴 Fork · 🐛 Issues · 🔧 PRs — see [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Author

**Uladzimir Dabranski** (D.U.P.)

- GitHub: [@Gruver87](https://github.com/Gruver87)
- Email: gruverpetrov@gmail.com

---

## License

[MIT](LICENSE) — free for learning and forks. **No warranty.** See [DISCLAIMER.md](DISCLAIMER.md).

---

*Last update: June 2026 — API Wave 61, real P2P topology/rejoin, Docker 3-node devnet, admin repair lockdown, 246 unit tests.*
