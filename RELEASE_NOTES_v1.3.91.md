# Release notes — v1.3.91

## Summary

**Native rustls TLS** for the v1.3.90 transport slice: `P2PNativeListener` / `P2PNativeConn` support mTLS (CERT_REQUIRED, hostname check off — same honesty as Python `p2p_tls.py`). Native + TLS can run together when material is valid.

## Changes

- `rustls` + `rustls-pemfile` in `abs_native`
- TLS handshake on accept/connect; `peer_cert_sha256` fingerprint getter
- `p2p_native_tls_available`; status `native_p2p_tls`; metric `abs_p2p_native_tls`
- Python no longer ignores `p2p_native_transport` when TLS is on (fail-closed if certs missing)
- `node_version`: `1.3.91-industrial`

## Honesty

- Still **not** libp2p / multiplex / full Rust message-loop ownership
- Handshake identity binding (CN/SAN ↔ node_id) remains Python control plane
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1391_p2p_native_tls.py -q
```
