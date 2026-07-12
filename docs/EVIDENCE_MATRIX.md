# Evidence matrix — what is proven vs not (Jul 2026)

**Purpose:** separate **automation that exists** from **operational evidence** collected on a live prod mesh.  
This doc reflects honest status after local prod mesh runs and monitoring — not marketing claims.

---

## Executive summary

**Absolute Blockchain Ultimate Hybrid** is a working R&D L1 / devnet stack with a functioning **3-node production-profile mesh** (chain `778888`), state synchronization, RocksDB hybrid persistence, Rust crypto on the hot path, automated CI/gates, and baseline ops tooling (health watch, DR rehearsal scripts, restart recovery).

**Public mainnet-ready readiness is not proven.** Missing confirmed evidence for: completed **24–48h+** soak and independent external security audit. **Cross-node EVM (mempool path) is now proven** on local prod mesh (Jul 12 evening).

Compared to documentation-only claims, **evidence level increased** in Jul 2026: real prod mesh bring-up logs, harness alignment, **7h soak passed**, **failover drill**, **signed tx propagation**, and **cross-node EVM (mempool deploy + 3 RPC storage)**.

---

## Live evidence run (2026-07-12, updated evening)

| Step | Result | Artifact |
|------|--------|----------|
| `health_watch.ps1 -ProdMesh -DurationMin 1` | **PASS** | `logs/evidence_health.log` |
| `prod_mesh_failover.ps1` | **PASS** | `logs/evidence_failover.log` |
| `prod_signed_tx_smoke.py` | **PASS** | `logs/evidence_signed_tx.log` (n2/n3 propagation) |
| `prod_evm_smoke.py` (mempool, 3 RPC) | **PASS** | docker mesh Jul 12 evening + **re-PASS block #7** Jul 12 post-v1.2.29 |
| `soak_monitor.ps1 -ProdMesh -Hours 7` | **PASS** | `logs/soak_report.json` (159 cycles, 0 fail) |
| `soak_monitor.ps1 -ProdMesh -Hours 48` | **IN PROGRESS** | `logs/soak_48h_v1.2.30.log` (started Jul 12 evening) |
| `testnet_readiness.ps1 -MinSoakHours 7` | **WARN** | re-run after mesh mining gate fixes recommended |

Full JSON template: [docs/evidence_run.example.json](evidence_run.example.json) (live runs: `data/evidence_run.json`, gitignored)

**Industrial fixes applied (Jul 12 evening):** mesh mining gate no longer latches on stale P2P wire roots; hub uses live STATUS heights; P2P broadcast non-blocking; `add_block` runs in worker thread so EVM apply cannot freeze the event loop; parallel peer state-root RPC.

**Lesson:** never use `/contract/deploy` direct on prod mesh for cross-node evidence — mempool signed deploy only. If split-brain occurs, rebuild without `-KeepVolumes`.

---

## Proven in live runs (Jul 2026)

| Claim | Evidence | How to reproduce |
|-------|----------|------------------|
| Prod 3-node mesh boots on RocksDB | `docker_prod_3node.ps1` → healthy containers, unified heights | `.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes` |
| Cross-node state / tip alignment | `GET /chain/consistency/harness` OK on :18180–:18182 | `.\scripts\probe_mesh_nodes.ps1 -ProdMesh` |
| P2P topology on prod ports | `peer_count=2`, `topology_healthy=True` in post-checks | same mesh script |
| **Failover / resilience** | node2 stop → mesh alive → node2 rejoin, heights aligned | `.\scripts\prod_mesh_failover.ps1` |
| **Signed tx propagation (prod)** | `prod_signed_tx_smoke.py` → n2/n3 see tx | `python scripts/prod_signed_tx_smoke.py` |
| **7h industrial soak** | `soak_report.json` passed, 159 cycles, 0 fail | `.\scripts\soak_monitor.ps1 -ProdMesh -Hours 7` |
| RocksDB DR path | DR rehearsal script + backup | `.\scripts\dr_restore_rehearsal.ps1 -DockerMesh1` |
| Short health monitoring | `health_watch` 1–2 min cycles, harness quick/full | `.\scripts\health_watch.ps1 -ProdMesh -DurationMin 2` |
| CI / static industrial gates | `industrial_gate.py`, prod_gate, pytest | GitHub Actions + local gate scripts |
| Native crypto required in prod profile | `ABS_REQUIRE_NATIVE_CRYPTO`, prod_gate | prod mesh configs |
| **EVM deploy + storage on all prod RPC peers** | Mempool deploy mined in block; `eth_getStorageAt` slot0=1 on all 3 RPC | `docker exec … prod_evm_smoke.py` (see evidence run) |

---

## Not yet proven (automation may exist)

| Gap | Why it is **not** proven yet | What would prove it |
|-----|------------------------------|---------------------|
| **24–48h soak** | **7h passed** (Jul 6–7); not yet 24–48h | `soak_report.json` with `hours_requested ≥ 24` |
| **External audit** | README and `external_audit_tracker.py` checklist incomplete | Third-party audit report + tracker items closed |
| **Bridge mainnet cutover** | Prod mesh runs with `bridge_enabled: false` by design | Audited L1 contracts + relayer SLOs per `docs/BRIDGE_L1_MAINNET.md`; decision recorded via `bridge_decision_off` step |
| **Ceremony + secret rotation automation** | **Scripts proven** (v1.2.32): `ceremony_preflight`, `rotate_prod_secrets.ps1` | Operator runs pin + `-Force` rotation before cutover — see `docs/MAINNET_CUTOVER.md` |
| **Public testnet / VPS** | Compose + nginx templates added; no production DNS/TLS deployment yet | Public URL, TLS, rate limits, 48h+ soak on testnet profile |

---

## Interpreting common log lines

| Log | Meaning |
|-----|---------|
| `SKIP: tx propagation (auto_sign disabled in prod)` | **Expected** on default prod mesh smoke — not a failure, but **not** proof of signed tx propagation |
| `SKIP: multi-node proof (testnet endpoints blocked in prod)` | Prod profile blocks dev testnet RPC helpers — use prod-signed smoke instead |
| `OK: soak passed` in &lt;1 second | **Bug / false positive** (fixed v1.2.21) — soak must run for `Hours × 3600` seconds |
| `External audit: not completed` | Honest organizational gate — see `scripts/external_audit_tracker.ps1` |

---

## Recommended proof sequence (before “mainnet-ready” language)

1. `.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes`
2. `.\scripts\prod_mesh_failover.ps1` — record block heights during node2 outage
3. `python scripts/prod_signed_tx_smoke.py`
4. `python scripts/prod_evm_smoke.py` — deploy + `eth_getStorageAt` on all prod RPC ports
5. `.\scripts\prod_evidence_suite.ps1` — health + failover + signed tx + EVM (optional one-shot)
6. `.\scripts\soak_monitor.ps1 -ProdMesh -Hours 48 -IntervalSec 300`
7. `.\scripts\testnet_readiness.ps1 -ProdMesh -MinSoakHours 48`
8. External audit tracker → third-party review

---

## Related docs

- [MAINNET_CUTOVER.md](MAINNET_CUTOVER.md)
- [MAINNET_GAP_ANALYSIS.md](MAINNET_GAP_ANALYSIS.md)
- [PUBLIC_TESTNET.md](PUBLIC_TESTNET.md)
- [STORAGE_ROCKSDB.md](STORAGE_ROCKSDB.md)
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md)
