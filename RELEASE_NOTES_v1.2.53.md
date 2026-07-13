# Release Notes — v1.2.53

Date: 2026-07-13

## Prod mesh in one command

```powershell
# Mesh already running (docker_prod_3node.ps1)
.\scripts\test_blockchain_full.ps1 -ProdMesh

# Bootstrap mesh + verify
.\scripts\test_blockchain_full.ps1 -ProdMesh -ProdMeshSpawn
```

Steps added:
- `probe_mesh_nodes.ps1 -ProdMesh -Deep` (topology + harness alignment)
- `verify_p2p_ci.py --mode prod-mesh3-live` on `:18180–:18182`
- `mainnet_readiness.py --live-prod-mesh`

## P2P improvements

- **Wire DoS guard:** drop P2P JSON lines larger than `p2p_max_message_bytes` (default 2 MiB)
- **Peer scores:** `/p2p/topology` and `/p2p/peer-score` include per-peer `score`, `peer_score_min`, `peer_score_avg`
- **Auto mode:** `verify_p2p_ci --mode auto` prefers prod mesh when all three prod ports are up

## Quick P2P checks

```powershell
.\scripts\probe_mesh_nodes.ps1 -ProdMesh          # deep probe by default
python scripts/verify_p2p_ci.py --mode auto       # prod mesh if up, else devnet, else CI
```
