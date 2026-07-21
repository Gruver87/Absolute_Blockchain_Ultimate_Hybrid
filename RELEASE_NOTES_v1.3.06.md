# Release notes — v1.3.06

**Date:** 2026-07-21  
**Theme:** CI honesty + housekeeping fail-closed + status/ops visibility

## CI

- `scripts/final_audit.py` is a **blocking** GitHub Actions step (soft-fail removed)

## P2P

- Housekeeping payloads (`ping`/`pong`/`get_mempool`/`get_peers`) reject junk (null or small typed objects only)
- Outbound `Peer.send` failures warn + increment `ops_errors.peer_send_fail`

## Status / ops

- `GET /status` → `p2p_hardening` includes `shape_rejects*`, `rate_limit_drops`, `handshake_rejects`, `active_bans`
- Topology snapshot failure still returns security counters when available

## Deploy / gate

- `P2P_EVICT_MIN_SCORE` in compose + k8s ConfigMap
- `industrial_gate` prints warning texts; optional `--fail-on-warnings`

## Verify

```powershell
.\scripts\post_soak_verify.ps1
python scripts/final_audit.py
```
