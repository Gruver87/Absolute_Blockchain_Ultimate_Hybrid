# docs/adr/0015-observability-secret-management.md
# ADR 0015 — Observability Port & Secret Manager Port

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Absolute Blockchain maintainers

## Context

`GET /metrics` was a monolithic `MetricsCollector.render_prometheus` call from
`RESTHandler` with no port boundary. TPS was missing from Prometheus (JSON
`/chain/metrics` only). Validator / BFT key material loaded from `wallet.json`
and `.env` with no `SecretManagerPort`; HashiCorp Vault was absent; K8s used
Opaque Secret → env examples only.

## Decision

1. **`MetricsExporterPort`** — frozen `MetricsSnapshot` DTO + Prometheus text
   render. HTTP ThreadingMixIn scrape builds the snapshot (sync reads:
   `peer_count`, `get_p2p_security_status`, height, chain window TPS) then
   calls the port. Does **not** run on the asyncio loop.
2. **Required series** — retain existing `abs_*`; add:
   - `abs_tps` — window tx / elapsed (fail-closed `0`)
   - `abs_p2p_security_ok` — `1` when P2P security snapshot succeeded
3. **`SecretManagerPort`** — logical secret ids (`node.wallet_private_key`,
   `node.bft_signing_key`, …). Package: `secret_mgmt/` (avoids shadowing
   stdlib `secrets`). Adapters: `EnvK8sSecretAdapter` (default),
   `VaultKvSecretAdapter`, `FileSecretAdapter` (dev; prod refuse).
4. **Boot** — resolve wallet / BFT material via SecretManager before
   `ValidatorKeys`; existing KMS / external `ValidatorKeyProvider` unchanged
   (sign-only).
5. **Fail-closed** — secret values never in logs, metrics labels, or DB meta.
   Prod refuses `SECRET_BACKEND=file|null`; FileSecretAdapter has no prod
   break-glass; boot does not swallow SecretManager init failure in prod.
   Vault in prod requires `https://` `VAULT_ADDR` (default SSL context).

## Honesty

- No `prometheus_client` dependency; hand-built text/plain 0.0.4 retained.
- Vault adapter is KV HTTP + token (AppRole / CSI out of scope).
- Gradual migration of JWT/RPC/bridge readers onto SecretManager is follow-up;
  sprint DoD focuses on wallet + BFT signing material.

## Definition of Done

- This ADR present; industrial_gate needles for ports + `abs_tps` + Vault/env
- `tests/unit/test_prometheus_export_format.py` green
- `tests/unit/test_secrets_isolation.py` green (no secret leakage to logs/DB)
- `/metrics` remains on ThreadingMixIn (off asyncio loop)
