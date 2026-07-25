# Release notes — v1.3.85

## Summary

Native **outbound egress bandwidth** (cost-weighted send QoS), symmetric to v1.3.78 inbound.

## Changes

- `P2PRateLimitTable`: separate `egress_byte_windows` / `egress_byte_limit` / `egress_rejects`
- `admit_egress` / `p2p_egress_admit` — reject reason `egress_bandwidth_exceeded`
- Same cost weights as ingress (`p2p_egress_cost_units`)
- `PeerConnection._egress_ok` gates `_send_loop` + priority fast-path before `writer.write`
- Config: `p2p_max_outbound_bytes_per_sec` (default 4 MiB/s, `P2P_MAX_OUTBOUND_BYTES_PER_SEC`)
- Prometheus: `abs_p2p_egress_rejects_total`, `abs_p2p_max_outbound_bytes_per_sec`
- `node_version`: `1.3.85-industrial`

## Honesty

- **Not** full Rust P2P transport: TCP/TLS, `readline` framing, send queue, message loop, and gossip/sync handlers stay Python
- Does not claim DoS immunity or public mainnet
- Ceremony pin + external audit remain org blockers; live mesh bridge OFF

## Verify

```text
python scripts/verify_industrial_waves.py
```
