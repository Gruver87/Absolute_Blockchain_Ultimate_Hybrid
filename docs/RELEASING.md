# Releasing

How Absolute Blockchain Ultimate Hybrid ships tags. Pattern matches industrial
waves already on `master` (v1.3.65+).

## Honesty first

- Tag green ≠ public mainnet
- `industrial_gate` may exit 0 with **warnings** (ceremony pin, external audit pending)
- Do **not** claim tip proof / libp2p / full Rust message-loop / completed external audit in release notes

## Checklist (maintainer)

1. **Implement** one Priority slice (Rust gate + Python control plane + tests).
2. **Build native** when Rust changed: `.\scripts\build_native.ps1` or `make build`.
3. **Verify:** `python scripts/verify_industrial_waves.py` (or `make test-quick`).
4. **Docs:** `RELEASE_NOTES_vX.Y.Z.md`, `CHANGELOG.md`, `docs/PORTING_ROADMAP.md`, version badge.
5. **Commit** (exclude `dist/` wheels).
6. **Tag** annotated: `git tag -a vX.Y.Z -m "…"`.
7. **Push** `master` + tag; `gh release create vX.Y.Z --notes-file RELEASE_NOTES_vX.Y.Z.md`.
8. Optional: confirm CI badges on the tag / release.

## Versioning

- `runtime/config.py` → `node_version = "X.Y.Z-industrial"`
- Git tag → `vX.Y.Z`
- Prefer one industrial Priority per tag (auditable history)

## Supply chain

- Dependabot: [`.github/dependabot.yml`](../.github/dependabot.yml)
- SBOM on release: [`.github/workflows/sbom-on-release.yml`](../.github/workflows/sbom-on-release.yml)
- Secrets: `python scripts/check_secrets.py`

## See also

- [SUPPORT.md](../SUPPORT.md)
- [docs/AUDITS.md](AUDITS.md)
- [SECURITY.md](../SECURITY.md)
