# Release v1.2.41 — prod mesh fork heal + mining gate (Jul 13, 2026)

## Summary

Fixes recurring **node1 solo-fork** on prod mesh (hub at h+1 with divergent state root vs node2/node3). Adds operational **fork heal**, **JWT-aware stabilize sync**, and **post-forge peer hold** so evidence runs stay truthful.

## Live evidence (local prod mesh :18180–:18182)

| Step | Result |
|------|--------|
| `mesh_stabilize.ps1` | **PASS** (cluster tip alignment; JWT fast-sync) |
| `health_watch.ps1 -ProdMesh -DurationMin 1` | **PASS** |
| `prod_mesh_failover.ps1` | **PASS** (recovery h41, topology healthy) |
| `prod_signed_tx_smoke.py` | **PASS** (n2/n3 confirmed) |
| `prod_evm_smoke.py` | **PASS** (mempool deploy, storage on 3 RPC) |
| `prod_evidence_suite.ps1 -RecordEvidence -GitTag v1.2.41` | **PASS** |

## Changes

### Mining / P2P

- **`runtime/mesh_mining.py`**: fail-closed mesh gate; wire `state_root` proof at local tip overrides stale P2P STATUS cache.
- **`main.py`**: always request wire roots before forge; **post-forge hold** until ≥2 peers confirm tip via wire RPC.
- **`network/p2p_node.py`**: STATUS echo refresh, state-root height update, reconnect status refresh, resilient catch-up loop.

### Ops scripts

- **`scripts/verify_p2p_ci.py`**: cluster-tip stabilize success; load `.env` JWT; pre-flight sync before failover; **auto-heal node1 fork** (optional `ABS_STABILIZE_AUTO_HEAL=0` to disable).
- **`scripts/mesh_heal_fork.ps1`**: clone node2 chainstore → node1 + rebuild/recreate.
- **`scripts/mesh_recover.ps1`**: `-HealFork` shortcut.
- **`scripts/prod_evidence_suite.ps1`**: failover pre-sync step.

## Operator notes

If stabilize shows `heights=N / N-1 / N-1` with HINT about node1 diverged:

```powershell
.\scripts\mesh_recover.ps1 -HealFork
.\scripts\prod_evidence_suite.ps1 -RecordEvidence -GitTag v1.2.41
```

`-RestartContainers` alone does **not** rebuild the image — use `-HealFork` or `mesh_heal_fork.ps1 -Force` after code fixes.

## Not proven by this release

- Completed **48h soak** (still in progress from v1.2.39 run)
- External audit, VPS/TLS public testnet, bridge mainnet cutover

See [docs/EVIDENCE_MATRIX.md](docs/EVIDENCE_MATRIX.md).
