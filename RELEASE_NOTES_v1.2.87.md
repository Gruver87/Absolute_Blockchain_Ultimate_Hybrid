# Release notes — v1.2.87

**Date:** 2026-07-21  
**Theme:** Industrial max polish — P2P TLS identity, bridge tooling, auth/gates (bridge still OFF)

## P2P

- TLS on ⇒ **CERT_REQUIRED** on server and client (no `CERT_NONE`)
- Handshake `node_id` bound to peer cert CN/SAN (`P2P_TLS_BIND_IDENTITY`)
- Optional peer cert fingerprint allowlist (`P2P_TLS_PEER_FINGERPRINTS`)
- All prod JSON profiles require P2P TLS + mTLS (incl. mainnet-v1 examples)
- `/p2p/security` exposes `fail_closed`, `identity_binding`, allowlist size
- Docs: [docs/P2P_TLS.md](docs/P2P_TLS.md)

## Auth / API

- JWT admin POSTs require `role=admin` (user tokens → 403)
- Dev `GET /auth/token?role=admin` for labs; prod mint: `python scripts/mint_admin_jwt.py`
- RPC API keys compared via HMAC + `compare_digest` (constant-time)
- GET routes share RPM limiter (`/health/*` exempt)

## Config / consensus honesty

- `bridge_enabled` default **false**
- Prod forces wallet file, TLS fail-closed/bind-identity; forbids `consensus_mode=parallel`
- Genesis strict addresses default **on** in prod (`GENESIS_STRICT_MAINNET=false` break-glass)
- PBS gated behind `feature_mev`; slash stats expose local-bookkeeping honesty
- Proposer attest failures fail-loud in prod

## L1 bridge (decision unchanged: OFF)

- Atomic L1 queue persistence
- Fail-loud `eth_getCode` on RPC errors
- Cutover gate: relayer probe exceptions are hard failures
- API: Solana not listed as production-supported
- Rust bridge subprocess stderr logged on failure

## Explicit non-goals (unchanged)

- External audit complete
- Live L1 contracts / public bridge enablement
- Satoshi tip `state_root` cutover
- Public VPS/DNS mainnet launch
