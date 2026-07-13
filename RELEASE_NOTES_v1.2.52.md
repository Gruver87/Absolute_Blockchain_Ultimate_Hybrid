# Release Notes — v1.2.52

Date: 2026-07-13

## One-stop full blockchain test

The master verification script now includes all automated mainnet-prep gates in one run:

- `scripts/test_blockchain_full.ps1` (Windows)
- `scripts/test_blockchain_full.sh` (Linux/macOS)

New steps (static, CI-safe):

- `industrial_gate.py`
- `mainnet_readiness.py --no-strict-audit --bridge-cutover`
- `bridge_l1_cutover.py` (static)
- `bridge_l1_preflight.py` on `node.prod.mainnet-v1.bridge.example.json`

`check_everything.ps1` is now a thin wrapper around `test_blockchain_full.ps1 -SkipNativeBuild`.

## Quick start

```powershell
# Full gate (builds abs_native + bridge if needed)
.\scripts\test_blockchain_full.ps1

# Faster local audit (skip native rebuild)
.\scripts\check_everything.ps1

# Live node on :8080
.\scripts\test_blockchain_full.ps1 -Live -P2P
```

Reports written under `data/` including `mainnet_readiness.json` and `industrial_gate.json`.
