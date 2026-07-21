# Release notes — v1.2.88

**Date:** 2026-07-21  
**Theme:** Soak honesty + Redis RL fail-closed + single-node P2P TLS

## Ops / soak

- `health_watch.ps1` exits **1** when hard FAIL port lines occurred (no soft-pass)
- `soak_monitor.ps1` requires wall-clock `hours_elapsed >= 0.95 * hours_requested`
- `industrial_gate --min-soak-hours` verifies elapsed duration, not only `hours_requested`

## Rate limit

- Prod + `REDIS_RATE_LIMIT=true`: no silent memory fallback; boot fails if Redis down
- Honest backend name in logs (`redis` vs `memory`)

## Docker / TLS

- `docker-compose.prod.p2ptls.yml` + `docker_prod.ps1 -P2pTls` for single-node
- 3-node TLS overlay docs updated for CN/SAN binding

## Mining honesty

- Log (and in prod clear consistency) on peer state-root / sync_state schedule failures

## Tests / SECURITY

- Coverage for `mint_admin_jwt` + prod_gate TLS on all profiles
- SECURITY.md: P2P TLS + Redis RL notes
