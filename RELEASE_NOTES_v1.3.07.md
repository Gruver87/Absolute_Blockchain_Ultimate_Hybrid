# Release notes — v1.3.07

**Date:** 2026-07-21  
**Theme:** Ops-error metrics + mid-session handshake fail-closed + prod rate hard errors

## Observability

- `GET /metrics`: `abs_p2p_peer_send_fail_total`, `abs_p2p_ops_errors{kind=…}`
- Alert `AbsoluteP2PPeerSendFailBurst` + Grafana panel

## P2P

- Mid-session `handshake` / `handshake_ack` → strike `mid_session_handshake` + `handshake_rejects`
- Those types removed from rate-limit exempt set (initial handshake still via `_do_handshake`)

## Gate / config

- industrial_gate **errors** if prod mesh JSON has `p2p_max_messages_per_sec <= 0`
- Warnings (TLS overlay, ceremony, external audit) remain non-blocking unless `--fail-on-warnings`
- `.env.example`: `P2P_HOST=0.0.0.0`

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
