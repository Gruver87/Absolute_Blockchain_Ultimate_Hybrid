# Release notes — v1.3.32

**Date:** 2026-07-21  
**Theme:** L1 receipt status, EVM static/corrupt fail-closed, NFT/PQ/will/multisig honesty

## Honesty / fail-closed

- Bridge L1 RPC: confirmations require receipt `status=0x1` (failed / status-less → not confirmed)
- EVM: corrupt storage and invalid calldata fail closed; `static_call` is read-only (reject nested CREATE / SELFDESTRUCT)
- NFT: gated by `feature_nft` (off in prod); stats expose `execution_bound` / `on_chain_standard`
- CryptoWill: `/will/execute` rejects `force=true` in prod
- Post-quantum: capability matrix (`educational_only`, no NIST claim); startup no longer greenwashes Kyber/Falcon
- Multisig: `execution_bound=false`, `persistent=false`, in-memory registry labels

## Config

- `node_version`: `1.3.32-industrial`
- Prod default: `FEATURE_NFT=false` (blocked like other R&D features)

## Tests / gates

- `tests/unit/test_v1332_honesty.py`
- Extended `test_l1_rpc.py` (failed / status-less receipts)
- Industrial gate needles for the above paths

## Explicit non-goals

- External audit · live L1 contracts · public mainnet launch · wiring BlockBuilder into forge · full bridge event-log binding
