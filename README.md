# ⚡ Absolute Blockchain Ultimate v40.0

> **Production-grade Ethereum-compatible client | LMD-GHOST Consensus | P2P Gossip | JSON-RPC**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-v40.0-blue.svg)](https://github.com/Gruver87/absolute-blockchain-ultimate/releases)

---

## 👤 Author

**Uladzimir Dabranski (Gruver87)**

- GitHub: [@Gruver87](https://github.com/Gruver87)
- Email: gruverpetrov@gmail.com

---

## 🚀 What's New in v40.0

- **LMD-GHOST Consensus** with validator attestations
- **P2P Gossip Network** (hash-first block propagation)
- **JSON-RPC API** (MetaMask / ethers.js compatible)
- **Multi-Node Devnet** (run 3 nodes simultaneously)
- **Strict LMD rule** (only latest attestation per validator)

---

## 🏗️ Architecture
┌─────────────────────────────────────────────────────────────┐
│ JSON-RPC API (Port 8545) │
├─────────────────────────────────────────────────────────────┤
│ CONSENSUS ENGINE (LMD-GHOST) │
│ • Strict LMD (latest attestation per validator) │
│ • GHOST cumulative subtree weights │
├─────────────────────────────────────────────────────────────┤
│ EXECUTION LAYER │
│ • Block builder + importer │
│ • Canonical chain (HEAD/SAFE/FINALIZED) │
├─────────────────────────────────────────────────────────────┤
│ P2P NETWORK │
│ • Real gossip protocol (hash-first propagation) │
│ • Seen cache + deduplication │
└─────────────────────────────────────────────────────────────┘

text

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate

# Install
pip install -r requirements.txt

# Run single node
python run_node.py --node-id node1 --rpc-port 8545 --p2p-port 30303

# Run devnet (3 nodes)
python run_devnet.py
🌐 Connect MetaMask
SettingValue
RPC URLhttp://localhost:8545
Chain ID1337
CurrencyABS
🧪 Run Tests
bash
python test_consensus_complete.py
python test_gossip_protocol.py
python test_node_runtime.py
📄 License
MIT License © 2025 Absolute Blockchain

⚠️ REMINDER: Experimental project — NOT for production use!
