# Audit scope letter — industrial L1

**Product:** Absolute Blockchain Ultimate Hybrid  
**Chain under review:** prod-profile `778888` (Docker 3-node mesh / future mainnet-v1)  
**Date:** 2026-08-07  
**Release pin:** tip-v2 industrial evidence on `master` (`375d14f` gates + `628cc9a`/`da25c34` docs); tag when auditor contracted (`v1.3.1339-tip-v2-industrial` or later)  
**Phase status:** Phase 2 tip-v2 48h PASS · Phase 3 ops dry-run PASS · Phase 4 audit binder READY (`docs/evidence/runs/phase4-691329c/`) — external firm engagement still TBD

## In scope

1. **Consensus tip path** — block import, tip-safety enforce, Path A catch-up, fork reconcile.  
2. **State / money** — satoshi storage dual-write; tip encoding v2 `b_satoshi` (ceremony-armed); StateService apply / fees / gas / reward.  
3. **P2P** — TLS/mTLS mesh, rate limits, soft-refuse, state_root solicit honesty.  
4. **API / RPC** — JWT admin, API keys, mempool-only contract deploy in prod.  
5. **Persistence** — RocksDB prod path, reorg index purge, DR rehearsal scripts.  
6. **Native crypto** — `abs_native` kernels on hot path (`ABS_REQUIRE_NATIVE_CRYPTO`).  
7. **Ops gates** — `industrial_gate`, `prod_gate`, `bridge_off_audit_gate`, evidence packs under `docs/evidence/runs/`.

## Explicitly out of scope

| Module | Reason |
|--------|--------|
| Shard lab (Profile E) | Separate mesh/DB; `feature_sharding=false` on prod |
| Plasma / Lightning / WASM / ZK / PQ | R&D; prod FEATURE_* false |
| Bridge ON / L1 lock-mint | Disabled until separate audited cutover |
| NFT / app staging | Profile C; not L1 trust path |
| Public mainnet ops / legal / listing | Organizational, not code audit of this tree |
| Full Ethereum client compatibility | EVM subset only |

## Deliverables expected from auditor

- Written report with severity ratings  
- Reproduction notes against tagged commit  
- Clear statement whether tip-v2 + apply path were in the reviewed build  

## Firm engagement

Placeholder — replace when contracted:

- Firm: _TBD_  
- SOW URL: _TBD_  
- Tracker: `scripts/external_audit_tracker.py` (do not mark complete until PDF lands in `audits/<firm>/`)

## References

- [THREAT_MODEL.md](THREAT_MODEL.md)  
- [AUDITS.md](AUDITS.md)  
- [STATE_ROOT_ENCODING_MIGRATION.md](STATE_ROOT_ENCODING_MIGRATION.md)  
- [MAINNET_GAP_ANALYSIS.md](MAINNET_GAP_ANALYSIS.md)  
