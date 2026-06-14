# Absolute Blockchain Ultimate

> **Educational Python blockchain node** — L1 core, REST/RPC, web explorer, PoS-style consensus, ABS tokenomics model.

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Educational%20Only-orange)]()
[![API Wave](https://img.shields.io/badge/API%20Wave-51-blue)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Unit%20Tests-210%20passed-brightgreen)](tests/unit/)
[![Release](https://img.shields.io/badge/Release-v1.2.0--industrial-blue)](https://github.com/Gruver87/absolute-blockchain-ultimate/releases)

**Repo:** [github.com/Gruver87/absolute-blockchain-ultimate](https://github.com/Gruver87/absolute-blockchain-ultimate)

| Field | Value |
|-------|-------|
| **Version** | `1.2.0-industrial` |
| **API Wave** | `52` → check `GET /status` → `api_wave` |
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

Honest one-screen view — no marketing claims beyond what is tested in-repo.

| Area | Level | Notes |
|------|-------|-------|
| **L1 chain** | 🟢 Strong demo | Blocks, balances, burn 2%, genesis, SQLite, ~15s blocks |
| **REST API** | 🟢 | 256+ routes, OpenAPI `/docs`, `api_wave=50` |
| **P2P 2-node** | 🟢 Verified | Docker + scripts; `state_roots_match=True` |
| **JSON-RPC** | 🟢 | `eth_*` subset, MetaMask-style |
| **Explorer UI** | 🟢 | SPA at `:8080` (32 tabs) |
| **EVM** | 🟡 Partial | Opcodes + logs SQLite; not full Ethereum parity |
| **L2 modules** | 🟡 Demo | Lightning, Plasma, WASM, Will, AI, MEV — SQLite + L1 effects where documented |
| **Bridge** | 🟡 Demo | `simulator` or `rust` binary; L1 RPC optional |
| **Production** | 🔴 Out of scope | By design |

**Tests (Jun 2026):** `210 passed, 1 skipped` · **Docker devnet:** 2 nodes, P2P sync, strict `state_root` policy

---

## Core L1 + P2P (Waves 47–51)

| Wave | Feature | Key endpoints |
|------|---------|---------------|
| **47** | TX receipts + chain metrics | `GET /chain/metrics`, `GET /tx/receipt/{hash}` |
| **48** | Address tx index | `GET /address/{addr}/activity`, `GET /address/{addr}/txs` |
| **49** | Block proposer audit | `GET /chain/proposers/stats`, `GET /chain/proposer/{addr}` |
| **50** | Strict `state_root` on P2P | `GET /chain/state-root/status` |
| **52** | **3-node testnet** | `GET /testnet/mesh`, `docker_devnet_3node.ps1` |
| **53** | **Fork / slashing CI** | `GET /testnet/fork-status`, `GET /slashing/events`, `--mode ci3` |
| **54** | **State consistency harness** | `GET /chain/consistency/harness`, `POST /chain/consistency/repair` |
| **55** | **5-validator devnet** | `GET /testnet/validators`, `docker_devnet_5validator.ps1` |

```powershell
(Invoke-RestMethod http://localhost:8080/status -UseBasicParsing).api_wave   # → 55
Invoke-RestMethod http://localhost:8080/testnet/validators -UseBasicParsing
Invoke-RestMethod http://localhost:8080/chain/consistency/harness -UseBasicParsing

# 5-validator devnet (Wave 55):
.\scripts\docker_devnet_5validator.ps1
python scripts/verify_p2p_ci.py --mode devnet5

# 3-node testnet (Wave 52):
.\scripts\docker_devnet_3node.ps1
python scripts/verify_p2p_ci.py --mode devnet3

# Adversarial CI (Wave 53, no Docker):
python scripts/verify_p2p_ci.py --mode ci3
# Send tx (node1 wallet auto_sign), then trace:
Invoke-RestMethod http://localhost:8080/tx/send -Method POST -ContentType application/json -Body '{"auto_sign":true,"to":"0x2222222222222222222222222222222222222222","value":0.01}'
Invoke-RestMethod http://localhost:8081/mempool -UseBasicParsing   # same tx on node2
Invoke-RestMethod http://localhost:8080/tx/trace/{hash} -UseBasicParsing
```

Full wave history (37–50): [CHANGELOG.md](CHANGELOG.md)

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
.\scripts\start_two_nodes.ps1 -RustBridge    # :8080 + :8081

# or Docker:
.\scripts\docker_devnet.ps1 -RustBridge
```

Expected when healthy:

```
OK: peers n1=1 n2=1 heights X / X state_consistent=True state_roots_match=True
api_wave=50
```

> After `docker compose up`, wait 15–30 s before API calls, or use `docker_devnet.ps1` (waits for readiness).

### Verify

```powershell
pytest tests/unit -q
curl.exe http://localhost:8080/health/live
curl.exe http://localhost:8080/status
curl.exe http://localhost:8080/chain/state-root/status
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
| `api_wave` &lt; 50 in Docker | `docker compose -f docker-compose.devnet-rust.yml build --no-cache node1` + recreate |
| Ports busy | `.\scripts\stop_node.ps1` |
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

*Last update: June 2026 — API Wave 55, 226+ unit tests, 5-validator devnet.*
