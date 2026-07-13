# Release Notes — v1.2.73

## Bridge L1 cutover evidence suite

Unified path before/after L1 contract deploy (soak deferred — RPC-only gate is the pre-deploy step):

```powershell
# Copy template and set ETH_RPC_URL in .env:
#   copy .env.bridge.cutover.example .env

# Before L1 contracts (placeholder 0x000… → WARN, not FAIL):
.\scripts\bridge_cutover_evidence_suite.ps1 -RpcOnly

# After L1 deploy + bridge-enabled prod node:
.\scripts\bridge_cutover_evidence_suite.ps1 -Full -Live
```

Runs: `bridge_l1_live_probe` → `bridge_l1_cutover` → `mainnet_readiness` → `industrial_gate`.

Report: `logs/bridge_l1_live_probe.json`

## Testnet VPS ops

```powershell
.\scripts\testnet_backup_restore.ps1 -DockerTestnetSeed -Rehearsal
```

```bash
# VPS cron (weekly)
bash scripts/testnet_log_rotate.sh
```

## Verify

```powershell
pytest tests/unit/test_bridge_cutover_evidence.py tests/unit/test_bridge_l1_cutover.py -q
```

## Next (operator)

- **48h soak** — `.\scripts\prepare_48h_soak.ps1` when ready (~2 days)
- **L1 contracts** — set `BRIDGE_L1_LOCK_CONTRACT` / `BRIDGE_L1_MINT_CONTRACT`, then `-Full`
