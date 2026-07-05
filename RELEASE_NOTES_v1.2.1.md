# Release v1.2.1 — Devnet ops & mainnet-v1 clarity

**Date:** 2026-07-05  
**Node version:** `1.2.0-industrial` · **API wave:** 61  
**Quality gate:** `698 passed, 1 skipped` (`pytest tests/ -q`)

---

## Summary

Operational and documentation release. No consensus rule changes. Focus: truthful deployment docs, mesh/solo diagnostics, light-client local sync, and explicit mainnet-v1 bridge cutover policy.

---

## Changes

### P2P / Dashboard / audit

- `GET /status` → `p2p_sync_status` (`solo`, `single_peer_dev`, `single_peer_stale`, `under_mesh`, `aligned`, …)
- `peers_connected`, `validators_registered`, `mesh_min_peers` on `/status`
- Explorer dashboard: peers as `connected / registered`, contextual P2P badges (not always “gap inconsistent”)
- `scripts/full_audit.py`: contextual INFO/WARN for solo vs stale peer vs prod under-mesh

### Bridge transparency

- `GET /status` → `bridge_disabled_reason` when bridge is off
- `GET /bridge/status` — alias of `/bridge` overview
- `setup_prod_env.ps1` writes `BRIDGE_ENABLED=false` by default (mainnet-v1 cutover policy)
- Prod mesh JSON (`docker/node.prod.mesh*.json`) keeps `bridge_enabled: false` until L1 contracts + relayer lab

### Light client

- `LightClient.sync_from_blockchain()` loads trusted local chain via sequential `add_header()` (fixes “0 headers synced” on solo node)
- `sync_headers_from_peers()` for untrusted peer header batches

### Ops tooling

- `scripts/probe_mesh_nodes.ps1` — probe `/status`, `/bridge/status`, `/features` on `:8080`–`:8084` (or `-ProdMesh` for 3-node prod)

### Tests

- `tests/unit/test_light_client_sync.py` — light client bootstrap + P2P/bridge status helpers

---

## Deployment matrix (truthful)

| Profile | Chain ID | HTTP ports | Bridge default | Verified by |
|---------|----------|------------|----------------|-------------|
| Solo dev | 77777 | :8080 | ON (rust/simulator) | `python main.py` |
| Docker 2-node | 77777 | :8080, :8081 | ON node1 | `docker_devnet.ps1` |
| Docker 3-node | 77777 | :8080–:8082 | per node JSON | `docker_devnet_3node.ps1` |
| Docker 5-validator | 77777 | :8080–:8084 | ON node1 only | `docker_devnet_5validator.ps1` |
| Prod mainnet-v1 solo | **778888** | :8080 | **OFF** | `setup_prod_env.ps1` + `python main.py` |
| Prod 3-node mesh | **778888** | :8080–:8082 | **OFF** | `docker_prod_3node.ps1` |
| Prod + bridge lab | **778888** | varies | ON (`-Bridge`) | `docker_prod.ps1 -Bridge` |

**Do not** run local `python main.py` on `:8080/:5000` while Docker mesh uses the same host ports — you will see solo mode or stale peers, not a mesh failure.

---

## Upgrade

```powershell
git pull
pip install -r requirements.txt
.\scripts\check_hybrid_full.ps1 -SkipNativeBuild   # or full native build
.\scripts\probe_mesh_nodes.ps1                     # after mesh up
```

---

## Not included (unchanged scope)

- No public mainnet launch
- No external security audit
- Bridge L1 cutover still requires real contracts, relayer ops, and `docker_prod.ps1 -Bridge` lab
- ABS remains an in-repo tokenomics model only

See [DISCLAIMER.md](DISCLAIMER.md) · [docs/MAINNET_GAP_ANALYSIS.md](docs/MAINNET_GAP_ANALYSIS.md)
