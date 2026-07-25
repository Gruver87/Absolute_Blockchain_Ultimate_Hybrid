# Release notes — v1.3.87

## Summary

Unified native **P2P egress prepare**: encode + allowlist + size + egress bandwidth admit in one kernel (`p2p_egress_prepare`), mirroring ingress admit.

## Changes

- `p2p_egress_prepare` in `native/abs_native/src/p2p_ingress.rs`
- `PeerConnection._prepare_outbound` wires send path (queue + priority)
- Status: `native_p2p_egress_prepare`
- `node_version`: `1.3.87-industrial`

## Honesty

- **Not** full Rust P2P transport: TCP/TLS, send queue, message loop, and gossip/sync stay Python
- Prepare unifies outbound policy only; framing (v1.3.86) and ingress admit remain separate
- Not public mainnet; ceremony pin + external audit remain org blockers; live mesh bridge OFF

## Verify

```text
python scripts/verify_industrial_waves.py
```
