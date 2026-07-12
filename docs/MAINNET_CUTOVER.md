# Mainnet cutover — operator sequence

**Purpose:** single honest path from local prod mesh to public mainnet cutover.  
Automation proves **scripts work**; production still needs coordinated validator ops and recorded evidence.

Related: [GENESIS_CEREMONY.md](GENESIS_CEREMONY.md), [SECRET_ROTATION.md](SECRET_ROTATION.md), [BRIDGE_L1_MAINNET.md](BRIDGE_L1_MAINNET.md), [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md).

---

## Decision tree

| Path | When | Bridge |
|------|------|--------|
| **Mainnet v1 (recommended first)** | Public L1 without bridge | `bridge_enabled: false` — current prod mesh default |
| **Bridge cutover** | Audited L1 lock contracts + relayer SLOs | `node.prod.mainnet-v1.bridge.example.json` + real `ETH_RPC_URL` |

Both paths require: ceremony deploy, secret rotation, 24–48h soak, external audit (organizational).

---

## Phase 1 — Ceremony (keys + hash pin)

```powershell
python scripts/genesis_ceremony_keygen.py --out-dir data/ceremony_keys
python scripts/ceremony_preflight.py --ceremony-dir data/ceremony_keys --strict-mainnet
.\scripts\deploy_ceremony_prod.ps1 -CeremonyDir data\ceremony_keys -Mesh
.\scripts\pin_ceremony_hash.ps1 -CeremonyDir data\ceremony_keys -StrictMainnet
```

Verify pin:

```powershell
python scripts/ceremony_preflight.py --ceremony-dir data/ceremony_keys --require-env-pin
```

---

## Phase 2 — Secrets

```powershell
.\scripts\setup_prod_env.ps1 -EthRpcUrl "https://<your-ethereum-rpc>" -Force
.\scripts\rotate_prod_secrets.ps1          # preview
.\scripts\rotate_prod_secrets.ps1 -Force   # apply before cutover
```

See [SECRET_ROTATION.md](SECRET_ROTATION.md).

---

## Phase 3 — Prod mesh + live evidence

```powershell
.\scripts\docker_prod_3node.ps1 -CeremonyDir data\ceremony_keys -SkipBuild -KeepVolumes
.\scripts\prod_evidence_suite.ps1
python scripts/mainnet_readiness.py --live-prod-mesh --ceremony-dir data/ceremony_keys --no-strict-audit
```

Record steps:

```powershell
python scripts/record_evidence_run.py --name prod_evm_smoke --result PASS --artifact logs/evidence_evm.log --git-tag v1.2.33
```

---

## Phase 4 — Soak (24–48h)

```powershell
.\scripts\restart_soak_prod_mesh.ps1 -Hours 48
# or foreground: .\scripts\restart_soak_prod_mesh.ps1 -Hours 48 -Foreground
.\scripts\testnet_readiness.ps1 -ProdMesh -MinSoakHours 48
python scripts/industrial_gate.py --min-soak-hours 48 --ceremony-dir data/ceremony_keys
```

**Note:** `restart_soak_prod_mesh.ps1` uses v1.2.31+ `health_watch` ProdMesh timeouts. Stop any prior soak PowerShell window before restarting to avoid duplicate monitors.

---

## Phase 5 — Bridge decision

### A) Bridge off (mainnet v1 default)

```powershell
python scripts/bridge_l1_preflight.py --config node.prod.mainnet-v1.example.json
# WARN: bridge_disabled — expected
python scripts/record_evidence_run.py --name bridge_decision --result PASS --notes "bridge_enabled=false for mainnet v1"
```

### B) Bridge on (after L1 contracts)

```powershell
$env:ETH_RPC_URL = "https://<production-ethereum-rpc>"
$env:BRIDGE_PROBE_L1_RPC = "true"
python scripts/bridge_l1_cutover.py --probe-l1
.\scripts\docker_prod.ps1 -CeremonyDir data/ceremony_keys -Bridge
.\scripts\bridge_l1_cutover.ps1 -Live -ProbeL1
```

Full stack gate:

```powershell
.\scripts\mainnet_live_gate.ps1 -CeremonyDir data/ceremony_keys -DockerLive -BridgeCutover
```

---

## One-shot automated checklist

```powershell
# Code gates + ceremony (no live mesh required)
.\scripts\mainnet_cutover_checklist.ps1 -CeremonyDir data\ceremony_keys

# + live prod mesh on :18180-18182
.\scripts\mainnet_cutover_checklist.ps1 -CeremonyDir data\ceremony_keys -LiveProdMesh

# + bridge static cutover (requires real ETH_RPC_URL)
.\scripts\mainnet_cutover_checklist.ps1 -CeremonyDir data\ceremony_keys -BridgeCutover
```

---

## Rollback

1. Stop nodes / `docker compose down`
2. Restore `.env` from `.env.bak.*` or manual backup
3. Set `bridge_enabled: false` if bridge cutover failed
4. Restore `data/bridge_l1_queue.json` from backup before drain
5. Re-run `ceremony_preflight` + `mainnet_readiness --live-prod-mesh`

---

## Honest blockers (not automated)

- Third-party security audit (L1 + bridge + EVM)
- Validator operator coordination at genesis
- Public DNS/TLS testnet or mainnet endpoints
- Legal / compliance review
