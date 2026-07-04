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

---

## Preflight

```powershell
$env:ETH_RPC_URL = "https://your-mainnet-rpc.example"
python scripts/bridge_l1_preflight.py --config node.prod.mainnet-v1.bridge.example.json
```

With bridge disabled (default v1):

```powershell
python scripts/bridge_l1_preflight.py --config node.prod.mainnet-v1.example.json
# WARN: bridge_disabled — expected until cutover
```

---

## Docker prod stack

```powershell
$env:JWT_SECRET = "<random>"
$env:RPC_API_KEYS = "<key>"
$env:BRIDGE_ORACLE_SECRET = "<random>"
$env:CORS_ORIGINS = "https://explorer.example.com"
$env:ETH_RPC_URL = "https://..."
$env:GENESIS_CEREMONY_HASH = "<from genesis_ceremony_keygen>"
.\scripts\docker_prod.ps1
python scripts/prod_smoke.py http://127.0.0.1:8080
python scripts/mainnet_readiness.py --live --base-url http://127.0.0.1:8080
```

Use `node.prod.mainnet-v1.bridge.example.json` as `--config` in `docker/node.prod.json` override when enabling bridge.

---

## Cutover checklist

1. Deploy contracts + record addresses in ops runbook (not in git if sensitive)
2. Switch config: `bridge_enabled: true`, `bridge_probe_l1_rpc: true`
3. Run relayer preflight: `python scripts/bridge_relayer.py --preflight --api http://127.0.0.1:8080`
4. Live smoke + readiness: `mainnet_readiness.py --live`
5. Monitor `/bridge`, `/bridge/relayer/status`, Prometheus `abs_l1_rpc_ok`

---

## Rollback

Set `bridge_enabled: false`, restart node, drain relayer queue (`data/bridge_l1_queue.json` backup first).
