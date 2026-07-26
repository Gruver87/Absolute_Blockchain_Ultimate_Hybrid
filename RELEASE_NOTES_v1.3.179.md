# Release notes — v1.3.179

## Summary

**Industrial mempool max-gas cheap refuse (no simplifications):**

1. **P2P max-gas refuse** — wire txs with `gas > evm_gas_limit` are refused **before** `validate_transaction` (ECDSA/state) (`gas_too_high`).
2. Soft DoS honesty under spam — **not** a Rust gas priority queue / EIP-1559 lanes.
3. Sequel to v1.3.177 (min-fee refuse) + v1.3.143 (dup cheap refuse).

## Changes

- `network/p2p_node.py` — gas ceiling gate in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_max_gas_refuse` / `P2P_MEMPOOL_MAX_GAS_REFUSE` (default on; ceiling = `evm_gas_limit`)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.179-industrial`

## Honesty

- Cheap ingress refuse — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust fee scheduler

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13179_mempool_max_gas_refuse.py -q
```
