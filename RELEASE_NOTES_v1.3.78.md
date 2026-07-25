# Release notes — v1.3.78

## Summary

Per-peer **inbound bandwidth budget** with cost-weighted units inside the native P2P ingress path (Priority 39 follow-on).

## Changes

- `P2PRateLimitTable`: `byte_limit`, `admit_bandwidth`, `bandwidth_rejects`
- `p2p_ingress_cost_units`: `blocks`/`block`/`mempool` cost ×2 vs raw bytes
- `p2p_ingress_admit` enforces budget after wire+rate → `bandwidth_exceeded`
- Config: `p2p_max_bytes_per_sec` (default 4 MiB/s)
- Metrics: `abs_p2p_bandwidth_rejects_total`, `abs_p2p_max_bytes_per_sec`
- `node_version`: `1.3.78-industrial`

## Honesty

- Inbound only; outbound byte QoS not claimed
- Not a full Rust P2P rewrite / not public mainnet
- Ceremony pin + external audit remain org blockers; bridge OFF on live mesh

## Verify

```text
python scripts/verify_industrial_waves.py
```
