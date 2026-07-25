# Release notes — v1.3.97

## Summary

**Native peer cert CN/SAN identities:** `P2PNativeConn.peer_cert_identities` extracts Common Name and SAN DNS/URI names from the rustls peer end-entity certificate. Native TLS handshake identity bind (`p2p_tls_bind_identity`) now works without an asyncio `writer`.

## Changes

- `extract_cert_identities` via `x509-parser` (CN + SAN DNS/URI, URI path tail)
- Getter `peer_cert_identities` on `P2PNativeConn`
- `_do_handshake` uses native identities for bind checks
- Status `native_peer_identities`; metric `abs_p2p_native_peer_identities`
- `node_version`: `1.3.97-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Handshake **policy** (validate payload, chain_id, allowlist) remains Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1397_p2p_native_peer_identities.py -q
```
