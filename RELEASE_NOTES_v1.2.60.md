# Release Notes — v1.2.60

## Fixes

- **`probe_mesh_nodes.ps1 -Deep`** — fixed PowerShell parser error (UTF-8 em dash in WARN string).
- **`verify_p2p_ci`** — `/p2p/security` 404 no longer hard-fails if `/p2p/topology.security` is present; missing `status.p2p_summary` on older containers is a WARN only.

## Prod mesh upgrade

Docker prod nodes use a baked image. After pulling v1.2.57+, rebuild:

```powershell
.\scripts\docker_prod_3node.ps1
# or without full ceremony redeploy:
.\scripts\docker_prod_3node.ps1 -SkipBuild:$false
docker compose -f docker-compose.prod.3node.yml -p abs-prod-mesh3 build --no-cache
docker compose -f docker-compose.prod.3node.yml -p abs-prod-mesh3 up -d
```

Then re-run:

```powershell
python scripts/verify_p2p_ci.py --mode auto --prefer-prod-mesh
.\scripts\probe_mesh_nodes.ps1 -ProdMesh -Deep
```
