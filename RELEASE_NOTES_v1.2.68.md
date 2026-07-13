# Release Notes — v1.2.68

## Bridge: `--probe-l1-rpc-only`

Your `--probe-l1` failures were **correct** — L1 contracts are still `0x000…` placeholders.

Before L1 deploy, validate RPC only:

```powershell
python scripts/mainnet_readiness.py --bridge-cutover --probe-l1-rpc-only --no-strict-audit
python scripts/industrial_gate.py --bridge-cutover --probe-l1-rpc-only
.\scripts\bridge_l1_live_probe.ps1 -ProbeL1RpcOnly
```

After L1 deploy + real addresses in `.env`:

```powershell
python scripts/industrial_gate.py --bridge-cutover --probe-l1
```

## VPS public testnet preflight

```powershell
.\scripts\prepare_vps_testnet.ps1
.\scripts\prepare_vps_testnet.ps1 -Live   # after docker_testnet_seed on :19080
```

Report: `logs/vps_testnet_preflight.json`

## Verify

```powershell
pytest tests/unit/test_bridge_l1_cutover.py tests/unit/test_vps_testnet_preflight.py -q
```
