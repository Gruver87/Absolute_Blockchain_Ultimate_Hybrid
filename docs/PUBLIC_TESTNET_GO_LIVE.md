# Public testnet go-live gate (Phase 5)

**Status:** blocked until industrial Phases 1–4 complete.  
**Do not** publish DNS/TLS until every checkbox below is true.

## Hard prerequisites

- [ ] `master` CI green (Tests + Security + Docker) on tagged industrial release  
- [x] Tip-v2 **48h soak** `passed=true` ([INDUSTRIAL_HARDEN_RUNBOOK.md](INDUSTRIAL_HARDEN_RUNBOOK.md) Phase 2) — Aug 5–7 2026; `docs/evidence/runs/375d14f/`  
- [x] Failover + signed tx + EVM re-smoke on tip-v2 — Aug 2 session (`docs/evidence/runs/8c92a51f0144/`)  
- [ ] Ceremony hash pinned + secrets rotation runbook executed on deploy host  
- [x] Bridge OFF gate PASS; no `bridge_enabled=true` on live public compose  
- [ ] External audit tracker: only remaining org items are firm-owned (or report landed)  
- [ ] [PUBLIC_TESTNET.md](PUBLIC_TESTNET.md) Go-live section + `vps_testnet_bootstrap*.sh` dry-run on target VPS  

## Go command (after checks)

```bash
# Linux VPS example — see PUBLIC_TESTNET.md
./scripts/vps_testnet_preflight.py
./scripts/vps_testnet_bootstrap_mesh3.sh
./scripts/prepare_testnet_dns_cutover.ps1   # or Linux equivalent docs
```

## Honesty

Public testnet is chain `77777` R&D — **not** mainnet-v1 `778888`.  
ABS is not a listed asset. No “mainnet-ready” language until [MAINNET_CUTOVER.md](MAINNET_CUTOVER.md) Phase complete + audit PDF in `audits/`.
