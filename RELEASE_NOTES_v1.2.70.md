# Release Notes — v1.2.70

## Public testnet 2-node mesh

Start seed + validator and verify P2P sync:

```powershell
.\scripts\docker_testnet_mesh.ps1
.\scripts\probe_testnet_mesh.ps1 -Deep
python scripts/verify_testnet_mesh.py --mesh --wait 120
```

Report: `logs/testnet_mesh_verify.json`

Configs set `testnet_expected_peers: 1` on seed and validator for `/testnet/mesh` health.

## Evidence suite with validator

```powershell
.\scripts\testnet_evidence_suite.ps1 -WithValidator
```

## Gate

```powershell
python scripts/public_testnet_gate.py --live --mesh
```

## Verify

```powershell
pytest tests/unit/test_verify_testnet_mesh.py -q
```
