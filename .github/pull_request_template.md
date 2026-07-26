## Summary

Brief description of what changed and **why**.

> Absolute Blockchain Ultimate Hybrid is a **production-hardened R&D / devnet** stack — **not** a launched public mainnet. Do not claim mainnet readiness without updating [docs/EVIDENCE_MATRIX.md](../docs/EVIDENCE_MATRIX.md).

## Related issues

Fixes #

## Type of change

- [ ] Bug fix
- [ ] Feature / industrial hardening (P2P / mempool / sync gate)
- [ ] Documentation / evidence honesty
- [ ] Tests / CI
- [ ] Security-related
- [ ] Dependabot / deps only

## Checklist

- [ ] `python scripts/check_secrets.py` clean (no secrets)
- [ ] Local verify: `.\scripts\operator_verify.ps1 -SkipNativeBuild` **or** targeted pytest for the wave
- [ ] Docs / release notes / `node_version` updated if this is a shippable wave
- [ ] No false “mainnet / audit complete / tip proof / libp2p” claims

## Test plan

- [ ] …
- [ ] (optional) `.\scripts\check_all.ps1 -Mode Standard`
