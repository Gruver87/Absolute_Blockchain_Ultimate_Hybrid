# Release notes — v1.3.66

## Load / backpressure industrial fixes

### What shipped

- ChainApplyQueue: enqueue deadline; skip expired jobs before dispatch
- P2P: mempool txs removed only after successful import
- Rocks: `chain_tip` meta + `RocksEngine.prefix_last` for tip lookup
- P2P: coalesce sync/connect tasks; bounded outbound send + drain timeout
- Metrics: apply expired/timeout/exec counters and sync task gauge

### Honesty

- Apply remains serial (admission/fairness, not parallel tip mutation)
- Not a public mainnet claim

### Version

- `node_version`: `1.3.66-industrial`
