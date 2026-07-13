# Release Notes — v1.2.71

## Public testnet 3-node mesh

Start seed + two validators and verify P2P sync:

```powershell
.\scripts\docker_testnet_mesh3.ps1
.\scripts\probe_testnet_mesh.ps1 -Mesh3 -Deep
python scripts/verify_testnet_mesh.py --mesh3 --wait 180
```

Report: `logs/testnet_mesh_verify.json`

Seed overlay sets `TESTNET_EXPECTED_PEERS=2` for `/testnet/mesh` health on a 3-node topology.

## Health watch

```powershell
.\scripts\testnet_health_watch.ps1 -Mesh3 -DurationMin 10 -IntervalSec 60
```

Log: `logs/testnet_health_watch.log`

## Evidence suite (3-node)

```powershell
.\scripts\testnet_evidence_suite.ps1 -Mesh3
```

## Gate

```powershell
python scripts/public_testnet_gate.py --live --mesh3
```

## Verify

```powershell
pytest tests/unit/test_verify_testnet_mesh.py tests/unit/test_public_testnet_gate.py -q
```
