# Release notes — v1.3.202

## Summary

**Industrial mempool max-value refuse (no simplifications):**

1. **Oversized value refuse** — P2P wire txs with `value` / `amount` above the cap are refused before `validate_transaction` (`value_too_high`).
2. Soft DoS honesty — fantasy amounts fail cheap before DB; default ceiling `221_000_000` ABS (aligns `max_supply`).
3. Sequel to v1.3.184 (negative value) / v1.3.193 (non-finite value) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — max-value check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_max_value_refuse` / `p2p_mempool_max_value` (default on / 221M)
- Env: `P2P_MEMPOOL_MAX_VALUE_REFUSE` / `P2P_MEMPOOL_MAX_VALUE`
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.202-industrial`

## Honesty

- Soft max-value gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not full tokenomics / amount-cap economics

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13202_mempool_max_value_refuse.py -q
```
