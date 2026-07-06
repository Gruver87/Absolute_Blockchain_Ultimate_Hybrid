# Evidence matrix — what is proven vs not (Jul 2026)

**Purpose:** separate **automation that exists** from **operational evidence** collected on a live prod mesh.  
This doc reflects honest status after local prod mesh runs and monitoring — not marketing claims.

---

## Executive summary

**Absolute Blockchain Ultimate Hybrid** is a working R&D L1 / devnet stack with a functioning **3-node production-profile mesh** (chain `778888`), state synchronization, RocksDB hybrid persistence, Rust crypto on the hot path, automated CI/gates, and baseline ops tooling (health watch, DR rehearsal scripts, restart recovery).

**Public mainnet-ready readiness is not proven.** Missing confirmed evidence for: live failover under block production, default prod-mesh signed-tx propagation, prod RPC EVM end-to-end, completed **24–48h+** soak, and independent external security audit.

Compared to documentation-only claims, **evidence level increased** in Jul 2026: real prod mesh bring-up logs, harness alignment, and soak monitoring runs — not only in-repo tests.

---

## Proven in live runs (Jul 2026)

| Claim | Evidence | How to reproduce |
|-------|----------|------------------|
| Prod 3-node mesh boots on RocksDB | `docker_prod_3node.ps1` → healthy containers, unified heights | `.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes` |
| Cross-node state / tip alignment | `GET /chain/consistency/harness` OK on :18180–:18182 | `.\scripts\probe_mesh_nodes.ps1 -ProdMesh` |
| P2P topology on prod ports | `peer_count=2`, `topology_healthy=True` in post-checks | same mesh script |
| RocksDB DR path | DR rehearsal script + backup | `.\scripts\dr_restore_rehearsal.ps1 -DockerMesh1` |
| Short health monitoring | `health_watch` 1–2 min cycles, harness quick/full | `.\scripts\health_watch.ps1 -ProdMesh -DurationMin 2` |
| CI / static industrial gates | `industrial_gate.py`, prod_gate, pytest | GitHub Actions + local gate scripts |
| Native crypto required in prod profile | `ABS_REQUIRE_NATIVE_CRYPTO`, prod_gate | prod mesh configs |

---

## Not yet proven (automation may exist)

| Gap | Why it is **not** proven yet | What would prove it |
|-----|------------------------------|---------------------|
| **Failover / resilience** | `prod_mesh_failover.ps1` exists but is **not** part of default `docker_prod_3node.ps1` post-check | `docker stop abs-prod-mesh3-node2-1` → blocks continue, quorum/mesh OK → `docker start …` → node rejoins and heights re-align |
| **Signed tx on default prod path** | `verify_p2p_ci` / mesh bootstrap prints `SKIP: tx propagation (auto_sign disabled in prod)` | Run `python scripts/prod_signed_tx_smoke.py` after mesh up; all 3 nodes see tx / mempool trace |
| **EVM end-to-end on prod RPC** | Opcode parity in CI ≠ live deploy/call on `:18180–:18182` | Signed deploy + contract call via prod JSON-RPC; state persisted and visible on peers |
| **24–48h soak** | Only short `health_watch` (~1h) and **in-progress** 7–10h `soak_monitor` at time of writing | `soak_report.json` with `passed: true`, `hours_requested ≥ 24`, zero mesh_warn / fail_lines |
| **External audit** | README and `external_audit_tracker.py` checklist incomplete | Third-party audit report + tracker items closed |
| **Bridge mainnet cutover** | Prod mesh runs with `bridge_enabled: false` by design | Audited L1 contracts + relayer SLOs per `docs/BRIDGE_L1_MAINNET.md` |
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
4. Prod EVM smoke (deploy + call on `:18180` RPC) — script TBD or manual checklist
5. `.\scripts\soak_monitor.ps1 -ProdMesh -Hours 48 -IntervalSec 300`
6. `.\scripts\testnet_readiness.ps1 -ProdMesh -MinSoakHours 48`
7. External audit tracker → third-party review

---

## Related docs

- [MAINNET_GAP_ANALYSIS.md](MAINNET_GAP_ANALYSIS.md)
- [PUBLIC_TESTNET.md](PUBLIC_TESTNET.md)
- [STORAGE_ROCKSDB.md](STORAGE_ROCKSDB.md)
- [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md)
