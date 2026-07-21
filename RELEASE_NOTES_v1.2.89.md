# Release notes — v1.2.89

**Date:** 2026-07-21  
**Theme:** Swiss-watch industrial pass — Redis mesh RL, JWT lazy secret, honesty + silent-fail purge

## Prod mesh

- Redis service + `REDIS_URL` / `REDIS_RATE_LIMIT=true` on all 3 prod mesh nodes
- `prod_gate` fails if mesh compose lacks Redis wiring

## Auth / rate limit

- JWT secret resolved from live `JWT_SECRET` (no freeze-at-import)
- Redis RL defaults **fail-closed**; mid-flight Redis errors deny
- Unit coverage for Redis incr failure + JWT post-import secret

## API honesty

- Bridge chain notes no longer claim “audited contracts”
- `/consensus/casper` and `/consensus/beacon` report `enabled:false` unless live
- Consistency repair surfaces `sync_error` and clears `_state_consistent` on failure

## Fail-loud critical paths

- Mining: proposer selection errors skip tick in prod (no silent weak fallback)
- P2P: local attest failures counted + logged (`attestation_local_fail`)
- Hybrid DB: aux migrate errors defer (do not mark migrated)
- Chain storage: no bare `except:`
- Consensus finality probe errors logged
- `full_audit` solo-node P2P is FAIL unless `FULL_AUDIT_ALLOW_SOLO_P2P_SKIP=1`

## Explicit non-goals (unchanged)

- External audit complete · live L1 contracts · public mainnet launch
