# Release Notes — v1.2.56

Date: 2026-07-13

## Monolith gate — one static report for the whole stack

```powershell
python scripts/monolith_gate.py --bridge-cutover
.\scripts\monolith_gate.ps1 -BridgeCutover
```

Layers combined (no duplicate industrial runs):

1. **Industrial gate** — native crypto, bridge smoke, mainnet readiness, runbook, EVM parity, prod gate
2. **Launch checklist** — K8s, DR backup drill, bridge preflight/cutover, ceremony/keys (skips gates already in industrial)

Report: `data/monolith_gate.json`

`test_blockchain_full.ps1` now calls monolith gate after bridge binary smoke (replaces 4 separate gate steps).

## P2P monolith hardening

- Per-peer rate limit: `p2p_max_messages_per_sec` (default **500**, `0` = disabled)
- Drops excess wire messages before handler (DoS/abuse mitigation)

## CI

GitHub Actions runs `monolith_gate.py --bridge-cutover` on Python 3.12 matrix.
