# Release notes — v1.3.86

## Summary

Native **NDJSON line framer** (`P2PLineFramer`): fail-closed buffered extract of `\n`-terminated frames before envelope parse / ingress admit.

## Changes

- New `native/abs_native/src/p2p_frame.rs` — `P2PLineFramer.feed` / `p2p_frame_feed_once`
- Reject `p2p_line_too_large` when pending exceeds max **before** newline; resync on next `\n`
- `PeerConnection._read_wire_line` prefers `reader.read(chunk)` + framer over `readline`
- Status: `native_p2p_framer`
- `node_version`: `1.3.86-industrial`

## Honesty

- **Not** full Rust P2P transport: TCP/TLS, send queue, message loop, and gossip/sync stay Python
- Framer is framing only; wire validate + rate/bandwidth remain separate kernels
- Not public mainnet; ceremony pin + external audit remain org blockers; live mesh bridge OFF

## Verify

```text
python scripts/verify_industrial_waves.py
```
