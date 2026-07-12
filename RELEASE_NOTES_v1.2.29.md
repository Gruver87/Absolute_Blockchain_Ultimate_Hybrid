# v1.2.29 — RLP in Rust (eth_sendRawTransaction hot path)

## Summary

Ethereum RLP encode/decode moved to `abs_native` for the real `eth_sendRawTransaction` / signed raw tx path. Python fallback kept for dev-only parity.

## Added

- `native/abs_native/src/rlp.rs` — `rlp_encode`, `rlp_decode`, `rlp_decode_single`
- `crypto/rlp.py` — delegates to native when wheel is present
- `tests/unit/test_rlp_native.py` — native vs Python reference parity
- Industrial gate + `native_crypto_status` self-test includes RLP roundtrip

## Verified

```powershell
pip install -e native/abs_native
python -m pytest tests/unit/test_rlp_native.py tests/unit/test_eth_raw_tx.py -q
python scripts/industrial_gate.py
```

Legacy / EIP-4844 signed tx decode paths unchanged at API level — now faster via Rust kernel.
