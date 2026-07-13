# Release v1.2.43 — Industrial hardening (Rocks reorg, audit gate, bridge checks) (Jul 13, 2026)

## Summary

Closes fork-safety gap on RocksDB secondary indexes, tightens mainnet audit gates, and validates bridge binary in industrial gate — without changing the intentional async bridge outbound flow (ABS receipt → L1 queue → relayer confirm).

## Changes

### RocksDB reorg (prod-critical)

- `reorg_truncate_above()` now purges **EVM logs** (`P_EVM_LOG`, `P_EVM_LOG_TX`) and **tx propagation** keys (`P_TX_PROP`) for blocks above the cut height
- Prevents stale log/trace data after fork on prod mesh

### Gates

- **External audit:** `External penetration test` and `Third-party smart-contract audit` require a real vendor note (not `auto:` placeholder)
- **Industrial gate:** `abs_bridge_bin` status smoke when binary exists
- **Prod gate:** mainnet-v1 default profile must keep `bridge_enabled=false` until L1 contracts deployed

## Bridge (honest status — unchanged behavior)

| Layer | Status |
|-------|--------|
| Rust CLI | Real L1 RPC receipt verification (ETH/BSC/Polygon) |
| Outbound lock | ABS-side deterministic receipt → `bridge_l1_queue.json` → relayer submits L1 tx |
| On-chain contracts | **Not in repo** — mainnet v1 ships bridge-off |
| Cutover lab | `node.prod.mainnet-v1.bridge.example.json` + `scripts/bridge_l1_cutover.py` |

## Still required for public mainnet

- [ ] 48h prod soak `passed=true` (`--min-soak-hours 48`)
- [ ] Third-party security audit (human sign-off)
- [ ] Genesis ceremony + validator ops
- [ ] Bridge L1 contracts (if bridge enabled at launch)

## Tests

```powershell
python -m pytest tests/unit/test_rocks_reorg_meta.py tests/unit/test_external_audit_human.py -q
python scripts/prod_gate.py
python scripts/industrial_gate.py
```
