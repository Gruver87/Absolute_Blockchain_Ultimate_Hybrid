# Release v1.2.42 — L2 advanced modules (working, not demo) (Jul 13, 2026)

## Summary

Lightning, Plasma, WASM VM, Oracles, and ZK modules upgraded from local simulations to **persisted, test-covered implementations** with real crypto primitives (secp256k1 state signatures, native Merkle proofs, HTLC lifecycle, wasmtime execution path, oracle quorum median).

These remain **R&D tier** — not full Bitcoin Lightning / Ethereum Plasma mainnet equivalents — but they are **functional end-to-end** with SQLite persistence and HTTP API.

## What is proven (unit tests)

| Module | Capability | Tests |
|--------|------------|-------|
| **Lightning** | L1 lock/unlock, channel payments, HTLC add/settle/refund, BFS routing | `test_wave40_*`, `test_l2_advanced_features` |
| **Plasma** | L1 deposit/exit, L2 transfers, block batching, native Merkle proof/verify | `test_wave40_*`, `test_l2_advanced_features` |
| **WASM VM** | Token ABI + deploy fee + persistence; wasmtime for binary WASM modules | `test_wave42_*` |
| **Oracles** | Reporter submissions + median quorum aggregation → canonical feed | `test_l2_advanced_features` |
| **ZK** | Schnorr knowledge, range, balance ≥ amount (Fiat–Shamir) | `test_zk_proofs` |

Run:

```powershell
python -m pytest tests/unit/test_l2_advanced_features.py tests/unit/test_wave40_l2_persistence.py tests/unit/test_wave42_wasm_relayer.py tests/unit/test_zk_proofs.py -q
```

## New / updated HTTP routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/lightning/htlcs` | List HTLCs |
| POST | `/lightning/htlc/add` | Lock HTLC |
| POST | `/lightning/htlc/settle` | Settle with preimage |
| POST | `/lightning/htlc/refund` | Refund after expiry |
| POST | `/lightning/route` | Multi-hop HTLC route |
| GET | `/plasma/proof?block_id=&tx_hash=` | Merkle inclusion proof |
| POST | `/oracles/reports/submit` | Reporter price report |
| POST | `/oracles/aggregate` | Quorum median |
| GET | `/oracles/aggregate/{symbol}` | Aggregate on read |

## Honest limits (not in this release)

- No on-chain L1 channel funding / watchtowers / full BOLT protocol
- No Plasma fraud proofs or operator bond slashing on L1
- Oracle network is registry + HMAC/quorum, not decentralized Chainlink-style nodes
- ZK balance/range proofs are R&D Fiat–Shamir, not audited Bulletproofs/snarks
- WASM custom contracts require **wasm binary (base64)** or built-in token ABI; WAT needs external `wat2wasm`

## Dependencies

- Optional: `wasmtime>=24.0.0` for binary WASM contract exports (`pip install wasmtime`)
