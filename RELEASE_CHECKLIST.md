Release checklist — Native hybrid production release

1. Ensure CI passes (all matrices) including native wheel build and smoke tests.
2. Confirm `native.native_crypto_status(required=True)` self-test passes on CI runners.
3. Run full test suite locally: `pytest tests/ -q` (expected 433 passed).
4. Cargo format & lint: `cargo fmt --all` and `cargo clippy` (fix issues).
5. Python linters: `ruff .` / `flake8` / `isort` (fix issues).
6. Secrets & prod gate: run `scripts/check_secrets.py` and `.\scripts\check_hybrid_full.ps1`.
7. Create release tag (semver): `git tag -a v1.2.0-industrial -m "Native hybrid release: hash-chain validation"`
8. Create GitHub Release with notes and attach wheel artifact if desired.
9. Update CHANGELOG.md with summary of native kernels and hybrid critical tests.
10. Communicate to ops: rollout plan, DB backup, and health checks (state_root consistency).

Notes:
- Use `ABS_REQUIRE_NATIVE_CRYPTO=true` in production to enforce native wheel availability.
- Keep `ABS_DISABLE_NATIVE_CRYPTO` for emergency rollback, but prefer feature flags and quick rollback releases.

