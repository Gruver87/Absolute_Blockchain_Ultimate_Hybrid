# Release notes — v1.3.73

## Apply-queue priority lanes

### What shipped

- `ChainApplyQueue` switched from FIFO `Queue` to `PriorityQueue`
- Order: **REORG / REORG_AND_IMPORT > FORGE_AND_APPLY > ADD > IMPORT**
- Equal priority stays FIFO via monotonic sequence
- Metrics: `abs_chain_apply_error_total`, `abs_chain_apply_priority_lanes`

### Why

Under multi-peer catch-up, import jobs could bury forge in a flat FIFO queue. Priority lanes keep mining and fork resolution ahead of bulk import without breaking serial tip safety.

### Honesty

- Still **one** serial worker (no parallel tip writes)
- Not a claim of full scheduler QoS or multi-lane apply throughput
- Not public mainnet; bridge OFF on live mesh

### Version

- `node_version`: `1.3.73-industrial`

### Verify

```powershell
python scripts/verify_industrial_waves.py
pytest tests/unit/test_v1373_apply_priority.py -q
```
