# Release notes — v1.3.12

**Date:** 2026-07-21  
**Theme:** Wire-probe fail-closed + import/sync counter honesty + ready/compose freeze

## Sync honesty

- `request_peer_state_roots_sync` returns `None` on timeout (not empty list)
- Empty probe with live peers → `wire_probe_ok=false`, `_state_consistent=false`, `sync_state` returns `False`
- Probe exceptions also fail-closed (no longer “consistent but probe failed”)

## P2P counters

- Soft `import_block` reject increments `import_block_fail`
- Batch sync uses `self.import_block`; stall/exception bumps `sync_fail`

## Ready / deploy

- Prod `/health/ready` requires `p2p_running` when P2P object exists
- Metrics sync gauges default fail-closed (unknown ≠ green)
- industrial_gate freezes `docker-compose.prod.yml` ↔ `node.prod.json`
- `.env.example` documents mainnet `778888` next to devnet `77777`

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
