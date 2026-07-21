# Release notes — v1.3.14

**Date:** 2026-07-21  
**Theme:** SQLite↔Rocks reorg parity + L1 probe honesty + slash/CORS fail-closed

## Storage

- SQLite `reorg_truncate_above` deletes `evm_logs` + `tx_propagation_events` (Rocks parity)
- SQLite `truncate_blocks_above` → full `truncate_chain_state` (no orphan txs/logs)
- Rocks reorg: corrupt TX/receipt/prop JSON → warn + delete (not ghost keys)

## Bridge / metrics

- Unprobed L1 RPC → `ok=false`, `error=probe_skipped`, `probed=false` (no green `abs_l1_rpc_ok`)
- Prometheus `abs_l1_rpc_probed`
- `_rust_bridge_health` import failure no longer NameErrors on L1 check

## Other

- `ConsensusAdapter.slash_validator` uses fail-loud DB path
- REST CORS empty origins → `""` (not `*`)
- industrial_gate freezes SQLite reorg + Rocks corrupt-TX + L1 probed surfaces

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
