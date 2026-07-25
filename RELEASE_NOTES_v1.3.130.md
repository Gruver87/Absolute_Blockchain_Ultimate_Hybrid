# Release notes — v1.3.130

## Summary

**Professional repo surface + industrial state_root soft head binding:**

1. **Repo professionalism** — Dependabot (pip/cargo/actions), EditorConfig, SUPPORT.md, docs/RELEASING.md, docs/AUDITS.md (honest pending), docs/REPO_PROFESSIONAL.md (peer comparison), SBOM-on-release workflow. No fake audit / mainnet claims.
2. **Soft `expected_head` on state_root waiters** — when the probe carries a local head digest, peer `head_hash` must match (plus existing height/digest gates). Empty expected_head skips the check.

## Changes

- `.github/dependabot.yml`, `.editorconfig`, `SUPPORT.md`, `docs/AUDITS.md`, `docs/RELEASING.md`, `docs/REPO_PROFESSIONAL.md`, `.github/workflows/sbom-on-release.yml`
- Rust/Python: `expected_head` on `verify_p2p_state_root_response_request_semantics` → strike `bad_state_root_response_head`
- `node_version`: `1.3.130-industrial`

## Honesty

- Still **not** cryptographic root-belongs-to-head / tip proof / external audit / libp2p / public mainnet
- Ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13130_p2p_state_root_expected_head.py -q
```
