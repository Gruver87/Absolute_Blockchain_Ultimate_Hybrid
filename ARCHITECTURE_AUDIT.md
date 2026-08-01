# Architecture Audit (legacy note)

> **Устаревший отчёт (июнь 2026).** Актуальная архитектура и mermaid: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** (ADR **0001–0016**, обновлено 2026-08-01).

## Current state (summary)

| Item | Value |
|------|-------|
| Entry point | `main.py` only |
| API | REST + JSON-RPC via QueryFacade (ADR 0011) |
| Consensus | Forest-stable LMD-GHOST · TipSafety + AncestryWindow |
| Secrets / metrics | `secret_mgmt/` · `observability/` (ADR 0015) |
| Tokenomics | 221M ABS, D.U.P. 17.4% · satoshi domain |
| Light client | `light/light_client.py` |
| Pool locks | `runtime/pool_locks.py` |
| Feature sprouts | ADR 0016 · `docs/sprouts/` (not kitchen-sink on 778888) |
| Legacy code | `_archive/` |
| Production profile | Fail-closed config, admin/RPC auth gates, Rust bridge proof requirement |

Run local audit:

```bash
python scripts/mega_audit.py
python scripts/final_audit.py
python scripts/prod_gate.py
```

**Current status:** production-hardened R&D/devnet node; not a launched public audited mainnet. Mesh chain sync is proven; stable `/health/ready` under TLS reconnect remains an open ops item.
