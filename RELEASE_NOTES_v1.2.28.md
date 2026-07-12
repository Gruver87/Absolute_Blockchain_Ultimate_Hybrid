# Release v1.2.28 — Industrial Phase 1 + native core hardening

## Summary

Fail-closed production deploy API, CI prod-mesh evidence (signed tx + EVM), and native-kernel alignment for block builder, cross-shard routing, and industrial gate.

## Added

- `_reject_direct_deploy_in_prod()` — `POST /contract/deploy` without `via_mempool` returns 400 in prod
- CI: `prod-mesh3` runs `prod_signed_tx_smoke.py` + `prod_evm_smoke.py` after consensus check (45 min timeout)
- Rust: `pubkey_to_eth_address` export in `abs_native`
- `KeyGenerator.derive_address_eth()` — Ethereum Keccak addresses (optional; chain identity stays legacy SHA-256)
- `docs/evidence_run.example.json` — template for live evidence JSON
- Tests: `test_api_prod_direct_deploy.py`, `test_block_builder_merkle.py`, `test_keygen_native.py`

## Fixed / hardened

- `execution/block_builder.py` — tx_root via `merkle_root()` (matches `core.blockchain.Block`); block hash via `native.canonical_hash_json`
- `consensus/cross_shard_coordinator.py` — shard routing digests via `native.hash_text`
- `crypto/keys.py` / `crypto/wallet.py` — address derivation via `native.sha256_hex` (stable vs prior hashlib)
- `main.py` — block signing failures logged instead of silent `pass`
- `crypto/native.py` — fail-closed `generate_proof`, `verify_proof`, `canonical_hash_json` when native required
- `scripts/industrial_gate.py` — abs_native self-test + critical export checks (`RocksEngine`, `evm_run_until_halt`, …)
- Docs synced: `MAINNET_GAP_ANALYSIS.md`, `EVIDENCE_MATRIX.md`, `README.md`

## Verify

```powershell
python -m pytest tests/unit/test_api_prod_direct_deploy.py tests/unit/test_block_builder_merkle.py tests/unit/test_keygen_native.py -q
python scripts/industrial_gate.py
pip install -e native/abs_native   # rebuild wheel after Rust changes
```

## Evidence status (unchanged gaps)

- 7h soak PASS; 48h soak still required
- External audit still open
