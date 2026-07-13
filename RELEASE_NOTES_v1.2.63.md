# Release Notes — v1.2.63

## Prod mesh3 recovery in CI

GitHub Actions (Linux) now runs **spawn + failover** in one step:

```bash
python scripts/verify_p2p_ci.py --mode prod-mesh3-ci-recovery --ceremony-dir data/ceremony_keys_ci
```

Flow: ceremony 3-node prod spawn on `:15280–15282` → signed tx / EVM evidence → **stop node2 process** → verify node1/node3 → restart node2 → P2P security checks.

Local Docker prod mesh (unchanged):

```powershell
.\scripts\prod_mesh_failover.ps1
.\scripts\docker_prod_3node.ps1 -KeepVolumes -NoCloneDb -RecoveryDrill
```

## Verify locally

```powershell
pytest tests/unit/test_p2p_industrial.py -q
python scripts/verify_p2p_ci.py --mode prod-mesh3 --ceremony-dir data/ceremony_keys_ci --recovery
```
