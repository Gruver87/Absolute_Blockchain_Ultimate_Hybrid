# Release notes — v1.3.40

**Date:** 2026-07-21  
**Theme:** Native Ethereum raw transaction decode kernel

## Rust / hybrid

- `decode_eth_raw_tx` / `decode_eth_raw_tx_hex` — legacy (EIP-155), EIP-1559 (0x02), EIP-4844 (0x03)
- Recover `from` via secp256k1 + keccak; reject unsupported typed txs (0x01 / 0x04)
- `crypto/eth_tx.py` prefers native JSON; falls back to Python RLP path

## Config

- `node_version`: `1.3.40-industrial`

## Tests / gates

- `tests/unit/test_v1340_eth_tx.py` + `tests/unit/test_eth_raw_tx.py`
- Industrial gate + post_soak needles for new symbols

## Explicit non-goals

- Full EVM host-in-apply · Rocks codecs · P2P rate-limit · public mainnet · bridge ON without audited L1
