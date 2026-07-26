---
name: Bug report
about: Report a reproducible defect in the hybrid node / mesh / gates
title: "[BUG] "
labels: ["bug"]
assignees: Gruver87
---

## Summary

Clear description of the failure.

## Environment

- OS:
- Python:
- Git tag / commit: (prefer latest industrial release tag)
- How you ran the node: `python main.py` / Docker prod mesh / other:

## Steps to reproduce

1.
2.
3.

## Expected vs actual

**Expected:**
**Actual:**

## Self-check already run?

```text
.\scripts\operator_verify.ps1 -SkipNativeBuild
# or: .\scripts\check_all.ps1 -Mode Quick
```

Paste the **FAIL** step + report path if the gate failed (`data/check_all.json`).

## Logs / artifacts

Paste relevant log lines (**redact secrets**). Link soak/probe artifacts if relevant.

## Checklist

- [ ] Not a secrets leak (no `.env`, keys, or wallet JSON)
- [ ] Checked [EVIDENCE_MATRIX](../../docs/EVIDENCE_MATRIX.md) — is this already a known gap?
- [ ] Not claiming “public mainnet / audit complete” without evidence
