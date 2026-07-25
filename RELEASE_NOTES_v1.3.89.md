# Release notes — v1.3.89

## Summary

**P2P Sybil / Eclipse hardening** on the native connection governor: public-only `/24`/`/64` subnet diversity, reserved outbound dial slots, eclipse ratio telemetry + prune, Prometheus metrics.

## Changes

- `P2PConnectionGovernor`: `max_peers_per_subnet`, `reserved_outbound_slots`, `diversity_snapshot`
- Helpers: `p2p_subnet_key`, `p2p_ip_is_public` (private/ULA/loopback exempt from subnet caps)
- `P2PNode._maybe_eclipse_prune` + `/p2p/security` eclipse fields
- Metrics: `abs_p2p_subnet_rejects_total`, `abs_p2p_reserved_slot_rejects_total`, `abs_p2p_eclipse_at_risk`, `abs_p2p_eclipse_ratio`, `abs_p2p_eclipse_prune_total`
- Config: `p2p_max_peers_per_subnet` (default 4), `p2p_reserved_outbound_slots` (2), `p2p_eclipse_warn_ratio` (0.34)
- `node_version`: `1.3.89-industrial`

## Honesty

- **Not** full Rust P2P transport (TCP/TLS/message loop still Python)
- **Not** ASN/BGP diversity or DHT peer exchange
- Subnet=/24|/64 is pragmatic IP diversity — **not** a complete Sybil-proof
- Docker private mesh (RFC1918) is intentionally exempt from subnet caps
- Not public mainnet; ceremony pin + external audit remain org blockers; live mesh bridge OFF

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1389_p2p_sybil_eclipse.py -q
```
