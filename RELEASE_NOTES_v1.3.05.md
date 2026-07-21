# Release notes — v1.3.05

**Date:** 2026-07-21  
**Theme:** Rate-limit fail-closed + P2P knob parity + Rocks alerts

## P2P fail-closed

- Per-peer rate-limit excess now strikes (`rate_limit_exceeded`) and bans — no silent drop-only
- Unexpected `recv` I/O errors → `WireReject("recv_error")` (not EOF)
- Prometheus: `abs_p2p_rate_limit_drops_total` + alert `AbsoluteP2PRateLimitBurst`

## Deploy / config honesty

- Prod mesh / k8s / examples pin: `p2p_max_message_bytes`, `p2p_max_messages_per_sec`, `p2p_ban_seconds`, `p2p_rate_limit_strikes`, `p2p_evict_min_score`
- Compose + ConfigMap env: `P2P_MAX_*` / `P2P_BAN_*` / `P2P_RATE_LIMIT_STRIKES`
- `.env.example`: P2P security block; `BRIDGE_ENABLED=false` (matches prod mesh / EVIDENCE_MATRIX)

## Rocks observability

- Alerts: `AbsoluteRocksBlockCacheUnset`, `AbsoluteRocksWriteBufferUnset` (when native crypto required)

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
