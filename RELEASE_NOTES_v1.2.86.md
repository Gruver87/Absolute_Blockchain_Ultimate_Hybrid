# Release notes — v1.2.86

## Pre-audit industrial polish (P0 security + P2P TLS default)

**Date:** 2026-07-21  
**Honesty:** prepares the stack for an **external audit engagement**. Does **not** claim audit complete or public mainnet.

### Security / fail-closed

- Prod `Config.apply_env` / `validate`: cannot weaken signatures, proposer, peer state_root, JWT admin, RPC keys; `RATE_LIMIT_RPM=0` and `ALLOW_INSECURE_PUBLIC_BIND` forbidden
- Slash persist / callback: fail-loud (no silent swallow)
- Rate limiter: prod requires working limiter; Redis errors fail-closed when Redis RL enabled; RPC auth ImportError fails start when required
- Compose: `mem_limit`/`cpus` + log rotation on prod + prod.3node
- External audit tracker: human items need real note + http(s) evidence URL (rejects `Vendor YYYY-MM-DD` templates)
- `industrial_gate` TLS warning reads prod mesh JSON (was dead on bare `Config()`)

### P2P TLS

- `docker_prod_3node.ps1`: TLS+mTLS overlay **default** (`-NoP2pTls` to opt out)
- Mesh JSON + compose overlay: `P2P_TLS_REQUIRE_CLIENT_CERT=true`
- Threat model documented in `docs/P2P_TLS.md` (no false cert↔identity binding claim)

### Evidence / docs

- Bridge decision **OFF** recorded for mainnet-v1 / pre-audit
- Soak checkbox synced in `STORAGE_ROCKSDB.md`
- Float tip-root known-limitation stamp for auditors

### Verify

```powershell
python scripts/prod_gate.py
python scripts/industrial_gate.py --min-soak-hours 48
pytest tests/unit/test_prod_config.py tests/unit/test_external_audit_human.py -q
```
