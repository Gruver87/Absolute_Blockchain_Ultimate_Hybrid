# Release notes — v1.3.04

**Date:** 2026-07-21  
**Theme:** Wire-reject fail-closed + ops metrics loop + Rocks deploy parity

## P2P wire rejects

- Malformed or oversized newline payloads no longer look like EOF
- `Peer.recv` returns `WireReject`; `_message_loop` strikes and counts `bad_wire_line` / `p2p_line_too_large`
- Shape-reject Prometheus series now cover garbage-on-the-wire attacks

## Observability

- Alerts: `AbsoluteP2PShapeRejectBurst`, `AbsoluteP2PHandshakeRejectBurst`, `AbsoluteP2PActiveBansHigh`
- Grafana panels for shape rejects, bans, Rocks CF / block cache
- `/metrics`: `abs_rocksdb_column_families`, `abs_rocksdb_block_cache_mb`, `abs_rocksdb_write_buffer_mb`

## Deploy parity

- `deploy/k8s/node.prod.k8s.json` + ConfigMap embedded JSON: Rocks tuning fields (CF default `false`)
- Mesh / mainnet example JSON aligned
- `k8s_prod_gate` + compose tests freeze `ROCKSDB_*`

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
