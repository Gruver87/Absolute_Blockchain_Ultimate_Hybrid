---
name: Ops / verify fail
about: Gate or mesh self-check fails locally — help triage without dumping secrets
title: "[OPS] "
labels: ["ops", "question"]
assignees: Gruver87
---

## What you ran

```text
.\scripts\operator_verify.ps1 -SkipNativeBuild
# or Mode Standard / Live
```

Exit code / last FAIL step:

## Environment

- OS:
- Python:
- Git tag / commit:
- Native wheel installed? (`abs_native` import OK?)

## Reports (paths only if large)

- `data/check_all.json`
- `data/verify_industrial_waves.json`
- `data/industrial_gate.json`

Paste the **error lines** (redact secrets), not full DB dumps.

## Checklist

- [ ] No `.env` / private keys / wallet JSON pasted
- [ ] Re-read [AT_A_GLANCE](../../docs/AT_A_GLANCE.md) — is the failure a known org blocker (ceremony pin / external audit)?
