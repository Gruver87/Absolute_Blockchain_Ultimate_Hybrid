# Architecture — Absolute Blockchain Ultimate

> Educational experimental node. Not production.

## Entry point

```
python main.py  →  NodeOrchestrator
```

All components are wired in `main.py` and passed to `api/http.py` (REST) and JSON-RPC thread.

## Layers

| Layer | Path | Role |
|-------|------|------|
| Runtime | `runtime/` | Config, tokenomics (221M ABS), pool locks |
| Core | `core/` | Blockchain, blocks, transactions, block headers |
| Storage | `storage/` | SQLite WAL, balances, meta, blocks |
| Consensus | `consensus/` | Adapter, epochs (32 blocks), slashing, finality |
| Execution | `execution/` | State engine, VM, block builder/validator |
| Network | `network/` | P2P, WebSocket |
| Features | `features/` | NFT, ZK, Lightning, Plasma, AI, etc. |
| Light | `light/` | SPV light client |
| API | `api/http.py` | 230 REST endpoints |
| Web | `web/explorer/` | 31-tab SPA |

## Data flow (mining)

```
Mempool → create_block() → add_block()
    → DB persist
    → immutable_state sync
    → light_client header
    → epoch boundary → pool_locks staking release
```

## Tokenomics enforcement

- `runtime/pool_locks.py` — ecosystem/treasury DAO lock, staking epoch release
- `core/blockchain.py` — `validate_transaction` / `_apply_transaction` checks
- Genesis: `runtime/tokenomics.py` → `genesis_balances()`

## Ports (default)

| Port | Service |
|------|---------|
| 8080 | HTTP REST + static explorer |
| 8545 | JSON-RPC |
| 8766 | WebSocket |
| 5000 | P2P |

## Legacy code

Old scripts (`level12_node.py`, `ABSOLUTE_*.py`, etc.) are removed or moved to `_archive/`.  
**Do not use them** — only `main.py`.

## Audit scripts

- `scripts/mega_audit.py` — syntax, endpoints, web coverage, tokenomics
- `scripts/final_audit.py` — wiring, runtime smoke tests

Reports: `data/final_audit_report.json` (local, gitignored `data/`)
