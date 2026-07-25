# Release notes — v1.3.90

## Summary

First **real Rust P2P transport slice**: plain-TCP `P2PNativeListener` + framed `P2PNativeConn` (accept/connect/read_line/write). Opt-in via `p2p_native_transport`. Python remains control plane (handshake, dispatch, gossip).

## Changes

- `native/abs_native/src/p2p_transport.rs` — listener + conn + framer I/O
- `P2PNode`: `_native_accept_loop`, `_handle_native_incoming`, native outbound connect
- Config: `p2p_native_transport` / `P2P_NATIVE_TRANSPORT` (default **false**; TLS incompatible)
- Metrics: `abs_p2p_native_transport`, `abs_p2p_native_accept_total`
- `node_version`: `1.3.90-industrial`

## Honesty

- **Not** full Rust P2P stack: TLS, asyncio message loop ownership, gossip/sync logic still Python
- **Not** libp2p / multiplex / noise
- Native path is **plain TCP only**; when TLS is on, flag is ignored (fail-closed honesty)
- Default remains asyncio transport so existing mesh/TLS configs are unchanged
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1390_p2p_native_transport.py -q
# Opt-in:
# $env:P2P_NATIVE_TRANSPORT="true"
```
