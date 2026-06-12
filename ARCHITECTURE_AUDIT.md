# Architecture Audit (legacy note)

> **Устаревший отчёт (июнь 2026).** Актуальная архитектура: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Current state (summary)

| Item | Value |
|------|-------|
| Entry point | `main.py` only |
| API endpoints | 230 |
| Web UI tabs | 31 (100% endpoint coverage) |
| Tokenomics | 221M ABS, D.U.P. 17.4% |
| Light client | `light/light_client.py` |
| Pool locks | `runtime/pool_locks.py` |
| Legacy code | `_archive/` |

Run local audit:

```bash
python _mega_audit.py
python _final_audit.py
```

**Educational project — not production.**
