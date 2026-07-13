# Release Notes — v1.2.54

Date: 2026-07-13

## Prod mesh FULL gate (one command)

After static pytest + base `-ProdMesh` checks, **`-ProdMeshFull`** runs the live operational evidence chain:

1. mesh stabilize + health watch
2. failover drill (`prod-mesh3-recovery` — stop/start node2)
3. signed tx propagation (`prod_signed_tx_smoke.py`)
4. EVM deploy + RPC storage (`prod_evm_smoke.py`)

```powershell
# Mesh must be up on :18180-:18182
.\scripts\test_blockchain_full.ps1 -SkipNativeBuild -ProdMeshFull

# Bootstrap mesh + full proof
.\scripts\test_blockchain_full.ps1 -ProdMeshFull -ProdMeshSpawn

# Record PASS/FAIL steps to evidence JSON
.\scripts\test_blockchain_full.ps1 -ProdMeshFull -RecordEvidence

# Shorthand alias
.\scripts\prod_mesh_full.ps1 -ProdMeshSpawn -RecordEvidence
```

Requires `.env` with `JWT_SECRET`, `RPC_API_KEYS`, and prod mesh wallets under `data/prod_mesh/wallets/`.

Optional tuning:

- `-ProdMeshFailoverWait 360` — recovery wait seconds
- `-EvidenceGitTag v1.2.54` — tag for `record_evidence_run.py`
