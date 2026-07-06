# Release v1.2.19 — mining stall fix

**Date:** 2026-07-06

## Summary

Fix prod mesh mining stuck at height 1 when P2P state_root RPC returns fewer than 2 responses (chain stopped for hours despite peers=2).

## Fixed

- **`runtime/mesh_mining.py`** — relaxed mesh mining gate: connected peers + sync consistency when wire responses are partial
- **`main.py`** — uses new gate instead of hard `len(wire_roots) < min_mesh_peers`

## Added

- `tests/unit/test_mesh_mining_ready.py`
- `tests/unit/test_rocks_reorg_meta.py` — Rocks reorg truncate tip metadata

## After upgrade

```powershell
git pull
docker compose -p abs-prod-mesh3 -f docker-compose.prod.3node.yml up -d --force-recreate node1 node2 node3
# or rebuild image if using local Dockerfile changes
```

Then optional 7h soak:

```powershell
.\scripts\soak_monitor.ps1 -ProdMesh -Hours 7 -IntervalSec 300
```
