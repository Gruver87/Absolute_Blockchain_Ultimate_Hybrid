# Release notes — v1.3.77

## Summary

Rust **P2P ingress data plane**: wire parse + primary/exempt rate in one native admit path, plus a connection governor (max peers / per-IP inbound). Python remains the control plane (gossip, sync, apply).

## Changes

- New `native/abs_native/src/p2p_ingress.rs`: `p2p_ingress_admit`, `P2PConnectionGovernor`
- `P2PRateLimitTable` gains `exempt_limit` + `exempt_rate_ok` / `admit_rate`
- `network/p2p_node.py` wires ingress in `PeerConnection.recv` / `_message_loop`
- Config: `p2p_max_inbound_per_ip` (default 8, `P2P_MAX_INBOUND_PER_IP`)
- `node_version`: `1.3.77-industrial`

## Honesty

- Not a full P2P rewrite to Rust
- Does not claim public mainnet / complete DoS immunity
- Bridge stays OFF on live mesh; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
```
