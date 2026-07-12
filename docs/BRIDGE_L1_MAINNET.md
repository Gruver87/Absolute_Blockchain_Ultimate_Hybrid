# Bridge L1 — Mainnet Enablement

**Profile:** `node.prod.mainnet-v1.bridge.example.json` (`bridge_enabled: true`)

Mainnet v1 default keeps bridge **off** until L1 lock contracts and RPC are production-ready.

---

## Prerequisites

- [ ] Audited L1 bridge contracts deployed (Ethereum / BSC / Polygon per policy)
- [ ] `ETH_RPC_URL` (and optional `BSC_RPC_URL`, `POLYGON_RPC_URL`) with production keys **via env only**
- [ ] `bridge/abs_bridge_bin` built and passing health smoke (`scripts/build_bridge.ps1`)
- [ ] `BRIDGE_ORACLE_SECRET` rotated; relayer sidecar healthy in `docker-compose.prod.yml`
- [ ] `BRIDGE_ALLOW_SYNTHETIC` **never** set in prod
- [ ] `GENESIS_CEREMONY_HASH` + `data/validators.manifest.json` from ceremony deploy

---

## Cutover gate (automated)

Static checks (bridge config + Rust CLI + placeholder RPC detection):

```powershell
$env:ETH_RPC_URL = "https://your-mainnet-rpc.example"
python scripts/bridge_l1_cutover.py
# or
.\scripts\bridge_l1_cutover.ps1
```

With live L1 probe (`eth_blockNumber`) and running Docker prod node:

```powershell
.\scripts\docker_prod.ps1 -CeremonyDir data/ceremony_keys
$env:ETH_RPC_URL = "https://your-mainnet-rpc.example"
$env:BRIDGE_PROBE_L1_RPC = "true"
.\scripts\bridge_l1_cutover.ps1 -Live
```

Full P0 stack including bridge cutover section in mainnet readiness:

```powershell
.\scripts\mainnet_cutover_checklist.ps1 -CeremonyDir data\ceremony_keys -BridgeCutover
.\scripts\mainnet_live_gate.ps1 -CeremonyDir data/ceremony_keys -DockerLive -BridgeCutover
```

When devnet occupies `:8080`, Docker prod listens on **`:18080`** (HTTP) and **`:18545`** (RPC).

---

## Preflight (bridge off — expected before cutover)

```powershell
python scripts/bridge_l1_preflight.py --config node.prod.mainnet-v1.example.json
# WARN: bridge_disabled — expected until cutover
```

Bridge profile static preflight:

```powershell
$env:ETH_RPC_URL = "https://your-mainnet-rpc.example"
python scripts/bridge_l1_preflight.py --config node.prod.mainnet-v1.bridge.example.json --probe-l1
```

---

## Docker prod stack

```powershell
.\scripts\setup_prod_env.ps1 -EthRpcUrl "https://your-mainnet-rpc.example" -Force
python scripts/genesis_ceremony_keygen.py --out-dir data/ceremony_keys
.\scripts\deploy_ceremony_prod.ps1 -CeremonyDir data/ceremony_keys
.\scripts\docker_prod.ps1 -CeremonyDir data/ceremony_keys
python scripts/prod_smoke.py http://127.0.0.1:18080
python scripts/mainnet_readiness.py --live --base-url http://127.0.0.1:18080 --ceremony-dir data/ceremony_keys
```

Docker uses `docker/node.prod.json` (`bridge_enabled: true`). Set `BRIDGE_PROBE_L1_RPC=true` in `.env` when L1 RPC is production-ready.

---

## Manual cutover checklist

1. Deploy contracts + record addresses in ops runbook (not in git if sensitive)
2. Set real `ETH_RPC_URL`, `BRIDGE_PROBE_L1_RPC=true` in `.env`
3. Run `.\scripts\bridge_l1_cutover.ps1 -Live`
4. Run relayer preflight: `python scripts/bridge_relayer.py --preflight --api http://127.0.0.1:18080`
5. Monitor `/bridge`, `/bridge/relayer/status`, Prometheus `abs_l1_rpc_ok`

---

## Rollback

Set `bridge_enabled: false`, restart node, drain relayer queue (`data/bridge_l1_queue.json` backup first).
