# Incident Response Runbook — Absolute Blockchain

**Version:** 1.0  
**Updated:** 2026-07-04  
**Scope:** Absolute Blockchain Ultimate Hybrid (L1 node, P2P, bridge, prod profile)

This runbook is the operational playbook for production and staging incidents.  
It complements automated gates (`prod_gate`, `mainnet_readiness`, `backup_db_drill`).

---

## Severity

| Level | Definition | Target response |
|-------|------------|-----------------|
| **SEV-1** | Chain halt, fund loss risk, key compromise | Immediate (< 15 min) |
| **SEV-2** | Partial outage, P2P partition, bridge stuck | < 1 hour |
| **SEV-3** | Degraded performance, single node drift | < 4 hours |
| **SEV-4** | Monitoring noise, non-user-facing | Next business day |

---

## Roles

| Role | Responsibility |
|------|----------------|
| **Incident commander** | Coordinates response, comms, rollback decision |
| **Node operator** | Restarts, logs, P2P mesh, DB backup/restore |
| **Security** | Key rotation, slashing review, bridge oracle |
| **Comms** | Status page, validator / user notification |

Maintain current on-call contacts outside git (password manager / ops channel).

---

## Detection

Automated signals:

- `GET /health/live` fails
- `GET /sync/status` → `state_consistent=false`
- `GET /chain/consistency/harness` → `harness_healthy=false`
- `python scripts/mainnet_readiness.py --live` fails
- `python scripts/verify_p2p_ci.py --mode prod-smoke` fails

Log locations: `data/node.log` (or `log_file` in node JSON), Docker stdout.

---

## SEV-1 — Chain halt / consensus emergency

1. **Stop propagation of bad state**
   - `.\scripts\stop_node.ps1` on affected hosts
   - Block new deployments until root cause known

2. **Identify tip divergence**
   ```powershell
   Invoke-RestMethod http://127.0.0.1:8080/status
   Invoke-RestMethod http://127.0.0.1:8081/status
   Invoke-RestMethod http://127.0.0.1:8080/chain/consistency/harness
   ```

3. **Check finalized floor** (no reorg below finalized checkpoint)
   - Review logs for `Reorg denied: below finalized floor`

4. **Recovery options**
   - Same-height fork: `POST /sync/reconcile` on lagging node
   - Long gap: `POST /sync/fast-sync` with `{"timeout":300}`
   - Fresh isolated mesh: `python scripts/verify_p2p_ci.py --mode prod-smoke`

5. **Escalate** if state roots diverge after reconcile → restore from backup (below).

---

## SEV-2 — P2P partition / peer loss

1. Verify ports: P2P (`p2p_port`), HTTP, bootstrap peers in config
2. `POST /p2p/reconnect` on each node
3. `python scripts/verify_p2p_ci.py --mode devnet` (or prod-smoke for prod profile)
4. If heights diverge > 20: prefer `-Fresh` devnet reset **only on testnet**, not mainnet
5. GHOST head: check `GET /consensus/slashing-engine` and reconcile status `ghost_head`

---

## SEV-2 — State root mismatch

1. `GET /chain/state-root/status` on all nodes
2. `POST /chain/consistency/repair` (non-prod admin JWT) — **blocked in prod**; use reconcile + reorg path
3. Compare genesis hash (deterministic per `chain_id`); mismatched genesis → new DB required
4. Run harness: `GET /chain/consistency/harness` on each node

---

## SEV-2 — Bridge / L1 RPC

**Mainnet v1 default:** `bridge_enabled: false` until audited contracts live.

If bridge enabled:

1. Verify `ETH_RPC_URL`, `BRIDGE_ORACLE_SECRET` rotated (not placeholders)
2. `GET /bridge/l1-queue` — stuck outbound/incoming
3. Pause bridge: set `bridge_enabled: false`, restart node
4. Never commit L1 keys; rotate via env / secret manager

---

## SEV-1 — Secret compromise

1. Rotate immediately: `JWT_SECRET`, `RPC_API_KEYS`, `BRIDGE_ORACLE_SECRET`, `ETH_RPC_URL` provider keys
2. Invalidate admin JWTs (`jwt_enforce_admin`)
3. Run `python scripts/check_secrets.py` before any push
4. Review validator manifest — no private keys in git
5. Document incident in post-mortem (outside repo)

---

## Disaster recovery (DB)

**Backup (online):**
```powershell
python scripts/backup_db.py --source data/blockchain.db --dest backups/chain-$(Get-Date -Format yyyyMMdd-HHmm).db
```

**Drill (verify backup integrity):**
```powershell
python scripts/backup_db_drill.py
python scripts/backup_db_drill.py --source data/blockchain.db
```

**Restore procedure:**

1. Stop node: `.\scripts\stop_node.ps1`
2. Move corrupted DB aside; copy backup to `data/blockchain.db`
3. Start node; verify `height`, `state_root`, `/health/live`
4. Re-sync peers: `POST /sync/reconcile`

**Multi-node:** restore **one** canonical backup to all validators only after chain-wide agreement.

---

## Post-incident

- [ ] Root cause documented
- [ ] `python scripts/external_audit_tracker.py --list` reviewed
- [ ] Tests re-run: `python scripts/industrial_gate.py`, prod-smoke if prod profile
- [ ] Update this runbook if procedure was wrong or missing

---

## Quick command reference

```powershell
.\scripts\stop_node.ps1
python scripts/industrial_gate.py
python scripts/prod_gate.py
python scripts/verify_p2p_ci.py --mode prod-smoke
python scripts/backup_db_drill.py
python scripts/mainnet_readiness.py --no-strict-audit --json
python scripts/external_audit_tracker.py --sync-automated
```
