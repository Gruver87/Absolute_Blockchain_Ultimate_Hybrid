# Release notes — v1.3.96

## Summary

**Native handshake I/O fuse:** `P2PNativeConn.handshake_roundtrip` performs the handshake / handshake_ack write+read in one Rust call. `P2PNode._do_handshake` uses it on the native transport path; payload validation, chain_id checks, and TLS policy remain Python.

## Changes

- `handshake_roundtrip(initiator, our_data_json, chunk_sz)` on `P2PNativeConn`
- Native TLS fingerprint path no longer requires asyncio `writer` for allowlist checks
- Status `native_handshake`; metric `abs_p2p_native_handshake`
- `node_version`: `1.3.96-industrial`

## Honesty

- Still **not** full Rust message-loop ownership (dispatch / strikes / gossip remain Python)
- Still **not** libp2p / multiplex / async runtime
- Handshake **policy** (validate payload, chain_id, identity bind) remains Python
- Native CN/SAN identity bind is best-effort (fingerprint allowlist works; full CN/SAN parse still asyncio TLS path)
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1396_p2p_native_handshake.py -q
```
