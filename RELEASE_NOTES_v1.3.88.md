# Release notes — v1.3.88

## Summary

**P2P kernel fuzzing** for `abs_native`: pure `fuzz_api` entry points, Windows/local **smoke** (`cargo test`), Linux **cargo-fuzz** targets (frame / wire / rate-limit) + CI workflow.

## Changes

- `native/abs_native/src/fuzz_api.rs` — `fuzz_p2p_frame_feed`, `fuzz_p2p_wire_parse`, `fuzz_p2p_rate_limit_sequence`
- `crate-type = ["cdylib", "rlib"]` + optional `extension-module` feature (maturin default unchanged)
- `native/abs_native/fuzz/` — cargo-fuzz targets `p2p_frame`, `p2p_wire`, `p2p_rate_limit`
- `scripts/fuzz_native.ps1` — `-Mode smoke` (default) / `-Mode fuzz`
- `.github/workflows/fuzz-native.yml` — smoke + short libFuzzer runs
- `node_version`: `1.3.88-industrial`

## Honesty

- Fuzz/smoke finds panics and fail-closed rejects; **not** a full security audit or memory-safety proof
- **Not** full Rust P2P transport (TCP/TLS/message loop still Python)
- Not public mainnet; ceremony pin + external audit remain org blockers; live mesh bridge OFF

## Verify

```text
python scripts/verify_industrial_waves.py
.\scripts\fuzz_native.ps1 -Mode smoke
```
