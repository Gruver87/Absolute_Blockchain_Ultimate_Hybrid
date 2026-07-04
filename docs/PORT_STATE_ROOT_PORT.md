Port plan: execution/state_root.py → Rust (abs_native)

Objective:
Port the heavy deterministic `state_root_from_accounts` computation into Rust/PyO3,
keeping byte-for-byte identical JSON canonicalization and preserving Python fallback.

Steps:
1. Create golden vectors (small account sets) and unit tests in `tests/unit/test_state_root_port.py`.
2. Implement Rust function `state_root_from_accounts_json` in `native/abs_native/src/lib.rs` (already present) or refactor into `state_root.rs` module and expose via PyO3.
3. Add CI smoke that builds the wheel and runs `tests/unit/test_state_root_port.py`.
4. Merge behind feature flag and monitor CI/perf.

Acceptance criteria:
- Native and Python implementations return identical state_root for golden vectors.
- CI builds wheel and passes smoke tests on Linux and Windows.
- No behavioral changes in existing tests.

Rollback:
- Keep Python fallback via `crypto/native.py` if `abs_native` is not available.

