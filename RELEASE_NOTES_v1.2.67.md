# Release Notes — v1.2.67

## L1 bridge live probe (`--probe-l1`)

Unified entry point for bridge cutover validation:

```powershell
# Load .env first (ETH_RPC_URL, BRIDGE_L1_* contracts)
.\scripts\bridge_l1_live_probe.ps1 -ProbeL1
.\scripts\bridge_l1_live_probe.ps1 -Full -BaseUrl http://127.0.0.1:18080
```

Report: `logs/bridge_l1_live_probe.json`

## Gates

```powershell
python scripts/mainnet_readiness.py --bridge-cutover --probe-l1 --no-strict-audit
python scripts/industrial_gate.py --bridge-cutover --probe-l1
.\scripts\monolith_gate.ps1 -BridgeCutover -ProbeL1
python scripts/verify_prod_stack.py --bridge-cutover --probe-l1
```

`--probe-l1` now works **without** `--live` (L1 RPC `eth_blockNumber` + contract bytecode checks).

## Verify

```powershell
pytest tests/unit/test_bridge_l1_live_probe.py tests/unit/test_bridge_l1_cutover.py -q
python scripts/bridge_l1_live_probe.py --probe-l1
```

See [docs/BRIDGE_L1_MAINNET.md](docs/BRIDGE_L1_MAINNET.md).
