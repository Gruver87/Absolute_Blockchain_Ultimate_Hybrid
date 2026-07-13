# Release Notes — v1.2.77

## P2P rate limit fix (prod mesh sync)

### Problem

During prod mesh catch-up, followers (`docker-prod-mesh-2`, `docker-prod-mesh-3`) logged:

```
[P2P] rate limit exceeded for docker-prod-mesh-1 (500/s)
```

The leader legitimately bursts `new_block`, `get_block`, `get_blocks`, and `new_tx` traffic above the default `p2p_max_messages_per_sec=500`. Those types were **not** in `RATE_LIMIT_EXEMPT_TYPES`, so messages were dropped and sync stalled.

### Fix

`network/p2p_node.py` now exempts all consensus/sync gossip types from the per-peer rate limit (same as `block` / `blocks` / `status`).

Rate limiting still applies to non-sync types (e.g. attestations, cross-shard) for DoS hardening.

### Verified (Jul 13, 2026)

Local prod mesh after v1.2.77 rebuild:

- `probe_prod_mesh.ps1` → **OK** (`logs/prod_mesh_probe.json`)
- 3/3 nodes reachable, height **182**, identical `head_hash` and `state_root`
- `harness_healthy` + `tip_state_aligned` on all nodes
- P2P TLS: **not enabled** on this run (`p2p_tls_enabled: false`) — enable separately via `docker_prod_3node_p2ptls.ps1`

### After upgrade

Rebuild and recreate prod mesh containers:

```powershell
docker compose -p abs-prod-mesh3 -f docker-compose.prod.3node.yml up -d --build --force-recreate node1 node2 node3
```

Confirm warnings stop and heights align:

```powershell
.\scripts\probe_prod_mesh.ps1
```
