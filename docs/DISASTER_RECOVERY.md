# Absolute Blockchain — Disaster Recovery Runbooks

**Audience:** SRE / DevOps / validator operators  
**Scope:** Absolute Hybrid node (`rocksdb` prod profile, chain id `778888` mainnet-v1 prep)  
**Honesty:** This is an **operations** document for a production-*profile* codebase. It is **not** a claim of a launched public mainnet or a completed external security audit.  
**Related:** [ADR 0014](adr/0014-graceful-shutdown-deep-health.md) · [ADR 0015](adr/0015-observability-secret-management.md) · [STORAGE_ROCKSDB.md](STORAGE_ROCKSDB.md) · [AUDITS.md](AUDITS.md) · [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md) · [SECURITY.md](../SECURITY.md)

---

## 0. Non-negotiable rules

1. **Never** kill `-9` / `taskkill /F` as the first step when RocksDB is open. Prefer graceful SIGTERM / Windows `CTRL_BREAK` so WriteBatch drains and `[RocksDB] clean close` lands (ADR 0014).
2. **Never** claim green consistency from harness alone. Prod recovery uses live P2P catch-up:
   - `POST /sync/fast-sync`
   - `POST /sync/reconcile`  
   `POST /chain/consistency/repair` and `POST /p2p/reconnect` are **prod-blocked (HTTP 403)**.
3. Admin mutations require **JWT** (`Authorization: Bearer <admin_jwt>`). Mint only from a controlled ops host; never embed tokens in tickets.
4. Before destructive disk work: **backup** `chainstore/` (and `aux.db` if present) off-box.
5. Validate after every runbook: `/health/live` → `/health/ready` → `/status` → `/metrics` (`abs_chain_height`, `abs_peers_connected`, `abs_p2p_security_ok`, `abs_tps`).

### Graceful stop (all platforms)

```powershell
# Preferred: stop script
.\scripts\stop_node.ps1

# Or: send CTRL_BREAK to a CREATE_NEW_PROCESS_GROUP child (Windows mesh / lab)
# POSIX containers: kubectl delete pod / docker stop → SIGTERM
```

Confirm in logs:

```text
[Node] Shutting down (graceful)...
[RocksDB] clean close (...)
[Node] Goodbye.
```

If the PID wedges after Goodbye, only then escalate to hard kill (ADR 0014 forces `os._exit` on signal drain; legacy wedged PIDs may still need `taskkill /T /F`).

---

## 1. Runbook — RocksDB Storage Corruption

### Symptoms

- Process crash / refuse boot with Rocks / storage errors
- Tip height present but block body missing (`tip_orphan` / tip fence warnings)
- `/health/ready` → `503` with `database` / `db_probe_error`
- Metrics: rising `abs_rocksdb_json_decode_failures` or engine snapshot failures
- Log: `[RocksAdapter] tip #N missing body — repair rewind to #M`

### Severity

| Class | Meaning |
|-------|---------|
| Soft | Orphan tip meta; bodies intact below tip |
| Hard | LSM / CURRENT / MANIFEST damage; open fails |

### Step A — Quiesce cleanly

1. Drain traffic (LB / remove from service mesh).
2. Graceful stop (section 0). Wait for clean close.
3. Snapshot the data dir **before** any repair:

```powershell
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$src = "C:\path\to\node\data"   # or /app/data
$dst = "D:\backups\abs-chainstore-$ts"
Copy-Item -Recurse -Force $src $dst
```

Python helper (offline, node stopped):

```powershell
python -c "from storage.chain_backup import backup_chainstore; print(backup_chainstore(r'C:\path\to\node\data', r'D:\backups\out'))"
```

Offline restore (node stopped): `storage.chain_backup.restore_chainstore(backup_dir, data_dir, force=True)` — only after verifying tip with `verify_chain_tip`.

### Step B — Tip repair on open (preferred soft path)

On every normal boot, `open_storage(..., repair_on_open=True)` runs Rocks tip fence repair (`RocksDBStorageAdapter.repair_tip_consistency`):

- Reads tip height
- Walks down until a block **body** exists
- `reorg_truncate_above` orphan tips
- Fail-closed `StorageCorruptionError` if repair cannot land on a body

**Operator action:**

1. Ensure `db_engine=rocksdb` and data path points at the same `chainstore/`.
2. Start the node once:

```powershell
python main.py --config path\to\node.prod.json
# or: .\scripts\start_node.ps1
```

3. Watch logs for rewind lines; then:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health/live
Invoke-RestMethod http://127.0.0.1:8080/health/ready
(Invoke-RestMethod http://127.0.0.1:8080/status).height
```

4. If peers exist and height lags, catch up (JWT required):

```powershell
$hdr = @{ Authorization = "Bearer $env:PROD_SMOKE_ADMIN_JWT"; "Content-Type" = "application/json" }
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/sync/fast-sync -Headers $hdr -Body '{"timeout":120}'
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/sync/reconcile -Headers $hdr -Body '{"timeout":120}'
```

### Step C — Nuclear wipe + peer fast-sync (hard corruption)

Use only if open/repair fails after backup.

1. Node **stopped**; backup already taken.
2. Remove only the hot store (keep wallet / TLS / config unless also compromised):

```powershell
# Example layout — adjust to your volume
Remove-Item -Recurse -Force C:\path\to\node\data\chainstore
# Do NOT delete validators.manifest / ceremony pins unless instructed
```

3. Ensure `bootstrap_peers` lists healthy validators with the canonical chain.
4. Start node. Empty store will genesis or follow `follower_genesis_sync` / catch-up policy from config.
5. Force catch-up:

```powershell
$hdr = @{ Authorization = "Bearer $env:PROD_SMOKE_ADMIN_JWT"; "Content-Type" = "application/json" }
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/sync/fast-sync -Headers $hdr -Body '{"timeout":300}'
Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8080/sync/reconcile -Headers $hdr -Body '{"timeout":300}'
```

6. DoD:
   - `/health/ready` → `200` with `deep_ready` / mesh checks green when mesh expected
   - Local height within peer quorum (gap ≤ 1)
   - `abs_p2p_security_ok 1` on `/metrics`
   - No continuous Rocks decode failure growth

### Forbidden

- Starting two processes on the **same** live `chainstore/` (LOCK corruption).
- Restoring a backup from a **forked** height without reconcile.
- Using `/chain/consistency/repair` in **prod** (403 by design).

---

## 2. Runbook — BFT Quorum Stall / Split Brain

### Symptoms

- Blocks stop advancing; `/status` height flat
- `/health/ready` → `503`: `sync_not_stalled=false` and/or `quorum_height=false` / `peers_alive=false`
- More than **⅓** of voting stake offline or partitioned (cannot reach ≥⅔)
- Peers report divergent tips (split view)
- Metrics: sync stall signals, peer count collapse, apply rejects climbing

### Honesty (read before acting)

- Prod consensus mode is **unified** (ADR 0007). `finality_quorum_live` is **not** invented from local attestation counts.
- There is **no** single magic RPC named `hard_reset_round` on the unified adapter.
- Industrial equivalent = **restore quorum connectivity + JWT-protected sync reconcile + controlled rolling restart**.
- `POST /consensus/engine/advance` advances the **standalone** `ConsensusEngine` slot only when that engine is enabled — it is **not** a substitute for unified mesh recovery.

### Step A — Triage (5 minutes)

```powershell
# Per affected node
Invoke-RestMethod http://NODE:8080/health/ready
Invoke-RestMethod http://NODE:8080/peers
Invoke-RestMethod http://NODE:8080/sync/status
Invoke-RestMethod http://NODE:8080/consensus/stats
Invoke-RestMethod http://NODE:8080/status | Select-Object height, consensus
```

Classify:

| Finding | Action branch |
|---------|---------------|
| `peers_alive=false` | Network / P2P first |
| Divergent heights across majority | Partition / fork — reconcile |
| Majority online, one lagging | Fast-sync the lagger |
| <⅔ stake reachable | Bring validators back before “reset” fantasies |

### Step B — Restore the validator set (preferred)

1. Confirm which validator hosts are down (process, disk, NIC, LB).
2. Bring offline validators back with **graceful** start; do not wipe storage unless Runbook 1 applies.
3. Wait until each reports peers and `/health/ready` (or documented mesh wait).
4. On the lagging node(s):

```powershell
$hdr = @{ Authorization = "Bearer $env:PROD_SMOKE_ADMIN_JWT"; "Content-Type" = "application/json" }
Invoke-RestMethod -Method POST -Uri http://LAGGING:8080/sync/fast-sync -Headers $hdr -Body '{"timeout":180}'
Invoke-RestMethod -Method POST -Uri http://LAGGING:8080/sync/reconcile -Headers $hdr -Body '{"timeout":180}'
```

5. Verify common head across the committee (heights equal; consensus mode `unified` where exposed).

### Step C — Forced round recovery sequence (protected admin path)

When the mesh is up but rounds will not advance (stall after partition heal):

1. **Freeze writes** at the edge (disable public tx admission if you front an API gateway).
2. Pick one **reference tip** (highest justified height held by ≥⅔ stake after reconcile).
3. On every node behind that tip: `POST /sync/fast-sync` then `POST /sync/reconcile` (JWT).
4. **Rolling graceful restart** of stalled members only (SIGTERM / `stop_node.ps1` → start). Keep ≥⅔ online at all times during the roll.
5. If standalone consensus engine is explicitly enabled in that lab profile (rare in prod unified):

```powershell
$hdr = @{ Authorization = "Bearer $env:PROD_SMOKE_ADMIN_JWT"; "Content-Type" = "application/json" }
Invoke-RestMethod -Method POST -Uri http://NODE:8080/consensus/engine/advance -Headers $hdr -Body '{}'
```

Treat this as a **lab / feature** lever, not the primary prod BFT dial.

6. Re-check `/health/ready`, height progress over 2–3 block intervals, and `abs_peers_connected`.

### Step D — Persistent split brain

1. Stop the minority fork validators gracefully.
2. Backup their `chainstore/`.
3. Either:
   - Wipe minority store and fast-sync from majority bootstrap peers (Runbook 1.C), or
   - Restore a known-good backup taken **before** the partition.
4. Never merge two incompatible tips by hand-editing LSM files.

### Forbidden

- Restarting **all** validators simultaneously (guarantees quorum loss).
- Prod use of `/p2p/reconnect` or `/chain/consistency/repair` (403).
- Declaring “finality live” from local attestation counts alone.

---

## 3. Runbook — Validator Key Compromise

### Symptoms

- Suspected leak of `WALLET_PRIVATE_KEY` / `BFT_SIGNING_KEY` / wallet.json `private_key`
- Unexpected signatures, slash events, or unauthorized admin JWT minting from stolen material
- Secret scanner / SIEM alert on key material in logs/tickets

### Goals

- **Revoke** compromised material via `SecretManagerPort` backends (ADR 0015)
- **Rotate** to a backup key
- Keep **committee quorum** (≥⅔) online — rotate **one** validator at a time

### Architecture reminder

| Layer | Role |
|-------|------|
| `secret_mgmt.SecretManagerPort` | Logical ids: `node.wallet_private_key`, `node.bft_signing_key` |
| `EnvK8sSecretAdapter` | K8s Secret → env (`WALLET_PRIVATE_KEY`, `BFT_SIGNING_KEY`) |
| `VaultKvSecretAdapter` | `SECRET_BACKEND=vault` + `VAULT_*` |
| `ValidatorKeyProvider` | Local wallet **or** external/KMS **sign-only** (no raw key in process) |
| `validators.manifest` | Public addresses / stake — update if the **address** changes |

### Step A — Immediate containment (minutes)

1. Remove the compromised validator from **public** ingress / P2P advertise if possible.
2. If the mesh still has ≥⅔ honest stake: **do not** halt the whole network.
3. Rotate any sibling secrets that may share the blast radius (`JWT_SECRET`, `RPC_API_KEYS`, bridge oracle HMAC) — compromise often clusters.
4. Open an incident record; do **not** paste private keys into chat/tickets.

### Step B — Revoke via SecretManager (env / K8s)

**Kubernetes Opaque Secret** (`deploy/k8s/secret.example.yaml` shape):

```powershell
# 1) Generate new key offline (air-gapped ops host) — store ONLY in secret backend
# 2) Patch Secret (example)
kubectl -n absolute-chain create secret generic abs-node-secrets \
  --from-literal=WALLET_PRIVATE_KEY=<NEW_HEX> \
  --from-literal=BFT_SIGNING_KEY=<NEW_HEX_OR_SAME> \
  --from-literal=JWT_SECRET=<NEW_JWT> \
  --dry-run=client -o yaml | kubectl apply -f -

# 3) Rolling restart ONLY the compromised StatefulSet pod
kubectl -n absolute-chain rollout restart statefulset/<validator-sts>
kubectl -n absolute-chain rollout status statefulset/<validator-sts>
```

Pod must mount secrets via `envFrom.secretRef: abs-node-secrets`. Boot path resolves keys through `build_secret_manager` → `SecretManagerPort` before `ValidatorKeys` init.

### Step C — Revoke via Vault

```text
SECRET_BACKEND=vault
VAULT_ADDR=https://vault.example:8200
VAULT_TOKEN=<ops token — never log>
VAULT_KV_PATH=secret/data/abs/node
```

1. Write new KV fields (`wallet_private_key` / `bft_signing_key`).
2. Invalidate old version / revoke previous Vault leases if used.
3. Restart **only** the compromised node so `VaultKvSecretAdapter` refreshes cache (TTL-aware).

### Step D — Address change vs same-address rotate

| Case | Actions |
|------|---------|
| Same address (re-key impossible for secp256k1 — normally **new key ⇒ new address**) | Treat as **new validator identity** |
| New address | Update `validators.manifest` / ceremony process; redeploy committee config; ensure stake/registry entries match; remove old address from active set |
| External/KMS provider | Rotate in HSM/KMS; update `EXTERNAL_VALIDATOR_SIGNER_*` via SecretManager; no raw key on disk |

### Step E — Validate isolation

1. Confirm new address appears in `/status` / validator APIs; old address no longer signs.
2. Grep ops logs for the **old** key hex — must be absent (ADR 0015 isolation tests encode this DoD).
3. Confirm DB meta was never used as a key store (`private_key` must not appear in chain meta).
4. Watch slashing / double-sign detectors if the attacker still holds the old key and attempts conflicting votes.

### Step F — “Without stopping the validation contour”

Meaning in practice:

1. Keep ≥⅔ **other** validators online throughout.
2. Rotate **one** compromised member via SecretManager + rolling pod restart.
3. Only after the new identity is admitted to the manifest/registry does the committee regain full N-of-N participation.

If compromise affects enough keys that stake <⅔ remains trusted: **halt public acceptance**, rotate keys offline, rebuild manifest, then cold-start the committee from a known tip (combine with Runbook 2).

### Forbidden

- Committing real keys to git / `wallet.json` in images.
- `SECRET_BACKEND=file` in prod (adapter **refuses**).
- Logging SecretManager resolved values (`repr` is redacted by design — keep it that way).

---

## 4. Prep for Point 10 — External audit (Trail of Bits / ConsenSys Diligence / equiv.)

**Status today:** external audit **not completed** — see [AUDITS.md](AUDITS.md). This section is the **auditor onboarding pack**, not a claim of audit done.

### 4.1 Where decisions live (ADR index)

| ADR | Path | Topic |
|-----|------|-------|
| 0001 | `docs/adr/0001-tip-safety.md` | Tip safety domain |
| 0002 | `docs/adr/0002-p2p-transport-boundary.md` | P2P transport ports |
| 0003–0005 | `docs/adr/0003-*.md` … `0005-*.md` | Sync / catch-up / fork reconcile |
| 0006 | `docs/adr/0006-storage-boundary.md` | Storage ports / UoW |
| 0007 | `docs/adr/0007-consensus-boundary.md` | Consensus ports / BFT SM |
| 0008–0009 | hotpath wire / native fallback | |
| 0010 | `docs/adr/0010-evm-bridge-boundary.md` | BridgePort |
| 0011 | `docs/adr/0011-rpc-api-boundary.md` | RpcPort / QueryFacade |
| 0012 | `docs/adr/0012-chaos-injection.md` | ChaosPort (lab only) |
| 0014 | `docs/adr/0014-graceful-shutdown-deep-health.md` | SIGTERM / deep ready |
| 0015 | `docs/adr/0015-observability-secret-management.md` | MetricsExporter + SecretManager |

*(0013 intentionally unused.)*

Also: `docs/EVIDENCE_MATRIX.md`, `docs/MAINNET_GAP_ANALYSIS.md`, `docs/PORTING_ROADMAP.md`, `SECURITY.md`.

### 4.2 Reproduce industrial maturity (commands)

From repo root:

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate_Hybrid

# Fast industrial gate (needles + ADR presence)
python scripts/industrial_gate.py

# Broad unit/integration offline suite (CI-scale; expect 1985+ on full tree)
python -m pytest tests/unit -q --tb=line

# ADR 0015 observability / secrets
python -m pytest tests/unit/test_prometheus_export_format.py tests/unit/test_secrets_isolation.py -q --tb=line

# Chaos smoke (always safe in CI)
python -m pytest tests/chaos -q -m chaos_smoke --tb=line

# Total chaos bombardment (lab evidence; ≥500 injections / ≤120s)
$env:CHAOS_FULL="1"
python -m pytest tests/chaos/test_total_chaos_bombardment.py::test_total_chaos_bombardment_2min -q -m chaos_full --tb=line

# Live mesh + physical kill (requires abs_native)
$env:LIVE_MESH_E2E="1"
python -m pytest tests/e2e/test_live_mesh_consensus.py -q -m live_mesh --tb=line

# Graceful SIGTERM / CTRL_BREAK Rocks clean close
$env:LIVE_MESH_E2E="1"
python -m pytest tests/e2e/test_runtime_signals.py -q -m live_mesh --tb=line

# Native build + fuller local gate (optional)
.\scripts\check_all.ps1 -Mode Full
```

**Honesty for auditors:** `main.py` / prod `NodeOrchestrator` **never** arms chaos. Chaos stays in `chaos/` + tests (ADR 0012).

### 4.3 What to hand the firm

1. This file + `docs/AUDITS.md` (status: pending).
2. ADR folder + Evidence Matrix.
3. Gate outputs: `python scripts/industrial_gate.py`, `python scripts/mainnet_readiness.py --no-strict-audit` (strict audit flag documents org blockers).
4. Tracker: `scripts/external_audit_tracker.py` / `.ps1` — close all checklist rows with evidence URLs after the engagement.
5. Scope proposal: P2P wire, Rocks tip fence, consensus ports, bridge atomicity, RPC DoS caps, secret isolation, graceful shutdown.
6. Out of scope until claimed: public mainnet, completed third-party report under `audits/<firm>/`.

### 4.4 Auditor DoD (Point 10 exit)

- [ ] Signed report PDF under `audits/<firm>/`
- [ ] Critical/High findings fixed or formally accepted
- [ ] `external_audit_tracker` items closed with evidence
- [ ] README / marketing **still** must not say “audited” until the above lands

---

## 5. Quick reference — recovery endpoints

| Method | Path | Prod | Purpose |
|--------|------|------|---------|
| GET | `/health/live` | yes | Liveness |
| GET | `/health/ready` | yes | Deep ready (peers / stall / quorum height) |
| GET | `/metrics` | yes | Prometheus (`abs_*`, ADR 0015) |
| POST | `/sync/fast-sync` | yes (JWT) | Catch-up |
| POST | `/sync/reconcile` | yes (JWT) | Fork reconcile |
| POST | `/chain/consistency/repair` | **403** | Dev/lab only |
| POST | `/p2p/reconnect` | **403** | Dev/lab only |
| POST | `/consensus/engine/advance` | JWT; standalone engine | Slot advance (not unified hard-reset) |

---

## 6. Escalation

1. On-call SRE → validator ops lead  
2. Security (key compromise) → rotate SecretManager backends + revoke JWT/RPC keys  
3. Protocol / consensus ambiguity → maintainers; cite ADR 0007 / 0014 / 0015  
4. External disclosure → [SECURITY.md](../SECURITY.md)

**Last updated:** 2026-07-30  
**Document owner:** Absolute Blockchain maintainers
