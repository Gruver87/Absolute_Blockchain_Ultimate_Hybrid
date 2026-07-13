# Release Notes — v1.2.74

## Prod mesh resilience (no soak)

Requires live prod mesh on `:18180-:18182`:

```powershell
.\scripts\docker_prod_3node.ps1 -CeremonyDir data/ceremony_keys
.\scripts\prod_mesh_resilience_suite.ps1
```

Steps: stabilize → probe → failover drill → post-failover probe → optional DR rehearsal.

Skip long steps:

```powershell
.\scripts\prod_mesh_resilience_suite.ps1 -SkipDrRehearsal
.\scripts\probe_prod_mesh.ps1 -WaitSec 120
```

Report: `logs/prod_mesh_probe.json`

## Genesis ceremony evidence

After offline keygen (`data/ceremony_keys/`):

```powershell
.\scripts\ceremony_evidence_suite.ps1 -CeremonyDir data/ceremony_keys
.\scripts\pin_ceremony_hash.ps1 -CeremonyDir data/ceremony_keys
```

Runs: `ceremony_preflight` → `mainnet_readiness --ceremony-dir` → `external_audit_tracker --sync-automated`.

## Deferred

- **48h soak** — `.\scripts\restart_soak_prod_mesh.ps1 -Hours 48` (~2 days)

## Verify

```powershell
pytest tests/unit/test_verify_prod_mesh_probe.py tests/unit/test_ceremony_preflight.py -q
```
