# Release Notes — v1.2.65

## 48h soak preflight (does not start soak)

Prepare prod mesh before a long soak run:

```powershell
.\scripts\prepare_48h_soak.ps1
# or
python scripts/soak_preflight.py --hours 48
```

Writes `logs/soak_preflight.json` with mesh health, P2P security, harness, topology, and the exact start command.

When you are ready to start the soak:

```powershell
.\scripts\restart_soak_prod_mesh.ps1 -Hours 48 -ReportFile logs/soak_report_48h.json
```

## Monolith gate

```powershell
python scripts/monolith_gate.py --soak-preflight
.\scripts\monolith_gate.ps1 -SoakPreflight
```

## Verify

```powershell
pytest tests/unit/test_soak_preflight.py -q
python scripts/soak_preflight.py --hours 48
```
