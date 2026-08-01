# Bridge cutover profile (Profile B)

Follow [BRIDGE_L1_MAINNET.md](../BRIDGE_L1_MAINNET.md) and
[ADR 0010](../adr/0010-evm-bridge-boundary.md). ADR 0016 places bridge enablement
in **Profile B**, separate from kitchen-sink FEATURE_* and from sharding.

## Invariants

- Live validators may keep `bridge_enabled=false` while a dedicated cutover
  node uses `node.prod.mainnet-v1.bridge.example.json`.
- Require `bridge_mode=rust`, L1 proof, non-placeholder RPC, no synthetic.
- Do **not** ship bridge cutover in the same release as `FEATURE_SHARDING`.
- Tip UoW remains untouched (bridge store atomic transitions only).

## Gate

```powershell
.\scripts\bridge_cutover_evidence_suite.ps1 -RpcOnly
# After contracts:
.\scripts\bridge_cutover_evidence_suite.ps1 -Full -Live
```
