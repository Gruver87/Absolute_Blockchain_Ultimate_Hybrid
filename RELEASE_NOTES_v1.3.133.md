# Release notes — v1.3.133

## Summary

**Industrial mesh bootstrap honesty (no simplifications):**

1. **Per-seed TLS pins** — `P2P_BOOTSTRAP_PINS` / `p2p_bootstrap_pins` bind configured bootstrap `host:port` to a cert SHA-256 fingerprint (optional `@node_id`). Impostors on the seed address do not satisfy coverage and are rejected at handshake.
2. **Coverage + redial** — with a pin set, `_peer_covers_bootstrap` requires fingerprint[/node_id] match; sticky resilient redial (v1.3.132) keeps dialing until the real seed appears.

## Changes

- `network/p2p_tls.py`: `bootstrap_pin_map`
- Handshake reject reasons: `bootstrap_pin_mismatch`, `bootstrap_pin_node_id_mismatch`, `bootstrap_pin_missing_tls`
- Metrics: `native_bootstrap_pin_gate`, `bootstrap_pin_rejects_total`, `bootstrap_pins_configured`
- `node_version`: `1.3.133-industrial`

## Format

```text
P2P_BOOTSTRAP_PINS=seed.example:5000=<sha256hex>@node-a,127.0.0.1:5001=<sha256hex>
```

## Honesty

- Soft pin of **configured seeds only** — not DHT trust roots, not tip proof, not libp2p peer IDs, not ceremony hash, not external audit
- Global `P2P_TLS_PEER_FINGERPRINTS` remain a mesh-wide allowlist; this is **addr→identity** binding

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13133_p2p_bootstrap_pins.py -q
```
