# Release notes — v1.3.128

## Summary

**Industrial mesh fail-closed hardening (no simplifications):**

1. **Discovery dialability policy** — `MSG_PEERS` / `GET_PEERS` gossip only dials/advertises addresses allowed by `p2p_peer_addr_is_dialable`. Literal RFC1918 / loopback / link-local / CGNAT are blocked unless `p2p_discovery_allow_private=true`. Docker DNS hostnames remain allowed. Bootstrap + post-handshake reconnect memory are not filtered (operator/explicit trust).
2. **Handshake + status soft height↔head binding** — height `> 0` requires a non-empty 32-byte hex `head_hash` (native loop-shell + Python handshake path). Blocks height inflation without a digest head. Not a tip existence proof.

## Changes

- Rust: `p2p_peer_addr_is_dialable_inner`, `verify_status_height_head_binding_inner`, `verify_handshake_head_semantics_inner`
- Config: `p2p_discovery_allow_private` / `P2P_DISCOVERY_ALLOW_PRIVATE` (default `false`)
- Metrics: discovery dial rejects + handshake/status soft-binding counters
- `node_version`: `1.3.128-industrial`

## Honesty

- Still **not** tip proof / fork-choice / DHT / libp2p / anti-Sybil identity / public mainnet
- Ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13128_p2p_discovery_and_head_binding.py -q
```
