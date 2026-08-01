# Evidence packages (Wave B)

Versioned, hashed mesh/ops artifacts. **Not** a substitute for external audit.

## How to package

```bash
python scripts/package_mesh_evidence.py \
  --out docs/evidence/runs/<commit-or-date> \
  --probe-log logs/probe_prod_mesh.txt \
  --soak-report logs/soak_report_48h.json
```

`manifest.json` binds `commit` + `sha256` of each file. Missing inputs are recorded as `status=missing` (honest).

## What belongs here

| Artifact | Proves |
|----------|--------|
| Probe log with `/health/ready` PASS ×3 | Mesh ready (Wave A) |
| Soak report `passed=true` | Long-run stability |
| Image digest / compose project id | Reproducible mesh image |

## Honesty

Historical Jul 2026 soak/failover claims in [EVIDENCE_MATRIX.md](../EVIDENCE_MATRIX.md) remain **operator-local** until a package for that SHA is committed or released as a GitHub Actions artifact.
