# Architecture Audit (legacy note)

> **Устаревший отчёт (июнь 2026).** Актуальная архитектура: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Current state (summary)

| Item | Value |
|------|-------|
| Entry point | `main.py` only |
| API endpoints | 288+ |
| Web UI tabs | 32 |
| Tokenomics | 221M ABS, D.U.P. 17.4% |
| Light client | `light/light_client.py` |
| Pool locks | `runtime/pool_locks.py` |
| Legacy code | `_archive/` |
| Production profile | Fail-closed config, admin/RPC auth gates, Rust bridge proof requirement |

Run local audit:

```bash
python scripts/mega_audit.py
python scripts/final_audit.py
python scripts/prod_gate.py
```

**Current status:** production-hardened R&D/devnet node; not a launched public audited mainnet.
