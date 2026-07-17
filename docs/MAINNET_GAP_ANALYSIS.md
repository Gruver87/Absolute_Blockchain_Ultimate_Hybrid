# Mainnet Gap Analysis — Industrial Blockchain Readiness

**Project:** Absolute Blockchain Ultimate Hybrid  
**Updated:** 2026-07-14  
**Positioning:** Production-hardened R&D stack → path to public mainnet  
**Evidence ledger:** [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md) — separates CI/automation from live ops proof

This document is the honest engineering checklist after a full repository scan.  
Automated gates (`mainnet_readiness`, `prod_gate`) enforce code-level fail-closed rules; **they do not replace** external audit, validator operations, or legal review.

---

## What is REAL (industrial-grade in-repo)

| Layer | Status | Notes |
|-------|--------|-------|
| L1 blocks, balances, burn, 221M cap | Real | `core/blockchain.py`, `runtime/tokenomics.py` |
| SQLite persistence + WAL prod mode | Real | Devnet default; **prod uses RocksDB** (`db_engine=rocksdb`) |
| RocksDB hybrid (prod hot path) | Real | `storage/hybrid_database.py`, DR rehearsal verified |
| P2P mesh 2/3/5 nodes | Verified CI | `network/p2p_node.py`, `verify_p2p_ci.py` |
| Native crypto (Rust PyO3) | Real | `native/abs_native`, `ABS_REQUIRE_NATIVE_CRYPTO` |
| State root + P2P import validation | Real | Wave 50–54 |
| EVM subset (Shanghai/Cancun) | Real subset | Not full Ethereum client |
| PoS proposer + slashing | Devnet-proven | Not formal BFT proof |
| NFT marketplace | Prod hybrid | RocksDB on prod hybrid (`HybridDatabase`); SQLite `aux.db` for cold/legacy modules only — see [STORAGE_ROCKSDB.md](STORAGE_ROCKSDB.md) |
| Prod config fail-closed | Enforced | `runtime/config.py`, `scripts/prod_gate.py` |

---

## What is DEMO / SIMULATOR (blocked in prod)

| Component | Tier | Prod blocked |
|-----------|------|--------------|
| `bridge/dev_bridge_adapter.py` | dev/test | Yes (`bridge_mode=rust` required) |
| `bridge/mock_l1_rpc.py` | CI only | Not loaded in prod |
| Plasma, Lightning | dev-test | `feature_*=false` in prod; v1.2.42+ implementations are **working R&D** (SQLite aux), not mainnet tier |
| WASM VM | r-and-d | Blocked in prod profile; wasmtime path for binary modules |
| ZK proofs | r-and-d | Blocked (Fiat–Shamir R&D) |
| Post-quantum Dilithium | r-and-d | Blocked (not NIST ML-DSA) |
| AI validator/agents | dev-test / analysis | Blocked |
| Sharding routing MVP | routing | Blocked |
| Oracles (weather/prices) | offchain | Blocked |

---

## Industrial hardening applied (2026-07-04)

1. **Mainnet readiness** — fails if external audit checklist incomplete (`strict_audit` default; use `--no-strict-audit` for dev only).
2. **Prod gate** — requires `cors_origins`, `evm_create2_eip1014`, `evm_require_deploy_salt`, non-devnet `chain_id`.
3. **EVM deploy** — production rejects deploy without `salt` (deterministic addresses).
4. **Bridge** — Solana rejected in prod rust path; L1 chains: ethereum, bsc, polygon, absolute.
5. **Rust bridge** — uses `l1_tx_hash` when provided instead of synthetic hash for confirm/incoming.
6. **Prod configs** — `chain_id: 778888` is official **MAINNET_V1_CHAIN_ID** (`runtime/mainnet_constants.py`).
7. **Prod smoke** — `python scripts/verify_p2p_ci.py --mode prod-smoke` (2-node prod mesh on :15180/:15181).
8. **Mainnet v1 profile** — `node.prod.mainnet-v1.example.json` (`bridge_enabled: false` until real L1 contracts).
9. **Ceremony keygen** — `scripts/genesis_ceremony_keygen.py` + `scripts/bridge_l1_preflight.py` in launch checklist.

---

## Live ops evidence (Jul 2026) — honest

### Demonstrated on prod mesh (:18180–:18182)

- [x] 3-node Docker mesh boot + height sync + harness alignment
- [x] RocksDB hybrid path + DR rehearsal script (`dr_restore_rehearsal.ps1`)
- [x] Short `health_watch` / monitoring cycles
- [x] CI + `industrial_gate.py` static checks

### **Demonstrated in live prod mesh runs (Jul 2026)**

- [x] **Failover under load** — `prod_mesh_failover.ps1` PASS (`logs/evidence_failover.log`; see [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md))
- [x] **Signed tx on prod mesh** — `prod_signed_tx_smoke.py` PASS (n2/n3 propagation; `logs/evidence_signed_tx.log`)
- [x] **EVM deploy/call on prod RPC ports** — `prod_evm_smoke.py` mempool path PASS (Jul 12 evening; storage on all 3 RPC)
- [ ] **Soak 24–48h+** completed with `soak_report_48h.json` passed (**48h RUNNING** since 2026-07-17 — `logs/soak_48h_v1.2.77.log`; **not completed**)
- [ ] **External security audit** — third-party firm; auto-checkmarks no longer satisfy strict gate (v1.2.43)

**API hardening (v1.2.28):** direct `POST /contract/deploy` without `via_mempool` is rejected in production — mempool signed deploy only.

---

## P0 — Blockers before public mainnet

- [ ] Complete all 8 items in `scripts/external_audit_tracker.py`
- [ ] Third-party security audit (L1 + bridge + EVM)
- [ ] Production validator manifest + offline keygen — **automation:** `ceremony_evidence_suite.ps1`, `deploy_ceremony_prod` (operator must run keygen + pin)
- [ ] Final `chain_id` (778888) + genesis ceremony hash pinned — **script:** `pin_ceremony_hash.ps1` + `--require-env-pin`
- [ ] Rotate all secrets — **script:** `rotate_prod_secrets.ps1 -Force` (see `docs/SECRET_ROTATION.md`)
- [ ] Live prod smoke: `python scripts/mainnet_readiness.py --live` (after docker prod or manual node)
- [x] Isolated prod mesh: `python scripts/mainnet_readiness.py --prod-smoke-spawn`
- [x] DR drill + incident response runbook (`dr_restore_rehearsal.ps1 -DockerMesh1`, `docs/INCIDENT_RESPONSE.md`)
- [ ] Decision: real L1 bridge contracts **or** disable bridge in mainnet v1 — **runbook:** `docs/MAINNET_CUTOVER.md` Phase 5

Operator sequence: [MAINNET_CUTOVER.md](MAINNET_CUTOVER.md).

---

## P1 — Core strengthening (next engineering waves)

| Area | Action |
|------|--------|
| EVM | CREATE/CREATE2 deterministic addresses (v1.2.79); EOF roadmap later |
| State | Dual-write `balance_satoshi` + StateEngine satoshi + **write-path unify** (v1.2.82: SQLite reset/nonce + adapter); tip root still float `"b"`; float column retained |
| Consensus | Single canonical fork-choice in prod (adapter + node skip parallel engines, v1.2.79) |
| Bridge | On-chain lock/mint contracts + monitored relayer (not proof-only) |
| Storage | RocksDB prod + backup/restore; **reorg purges EVM/tx-prop indexes** (v1.2.43); aux.db scope documented |
| State root | Prod refuse tip header rewrite (`allow_state_root_rewrite=false`, v1.2.79) |
| Tests | ✅ CI: `industrial_gate.py`, prod boot E2E, `verify_p2p_ci --mode prod-smoke` |

---

## P2 — Post-launch / optional

- Distributed sharding (after stable single-chain mainnet)
- L2 modules remain dev-test unless independently audited
- ZK / PQ only after crypto audit and real implementations

---

## Commands

```powershell
# Unified monolith static gate (industrial + mainnet + launch checklist)
python scripts/monolith_gate.py --bridge-cutover
.\scripts\monolith_gate.ps1 -BridgeCutover

# Full local verification
.\scripts\test_blockchain_full.ps1 -SkipNativeBuild

# Live prod mesh proof
.\scripts\test_blockchain_full.ps1 -ProdMeshFull -ProdMeshSpawn
python scripts/mainnet_readiness.py --live-prod-mesh --no-strict-audit
```

```powershell
# Industrial static gate (no external audit blockers)
python scripts/industrial_gate.py
python scripts/industrial_gate.py --prod-smoke-spawn

# Strict mainnet gate (fails until external audit complete)
.\scripts\mainnet_readiness.ps1

# Dev automation only (warnings, not blocking on audit)
python scripts/mainnet_readiness.py --no-strict-audit --json

# Track organizational checklist
.\scripts\external_audit_tracker.ps1 -List

# Production static gate
python scripts/prod_gate.py

# Full release before tag
.\scripts\release_gate.ps1 -Mainnet -SkipNativeBuild
```

---

## Honest summary

The codebase is a **serious industrial devnet / private testnet** implementation with **rising live evidence** (prod mesh runs, harness, monitoring) — not merely documentation claims.

**Public mainnet launch** still requires organizational gates (external audit, validator ops, genesis ceremony in production) plus **remaining operational proof**: completed **24–48h soak** and bridge cutover decision. Failover, signed-tx propagation, and cross-node EVM (mempool) are demonstrated on local prod mesh (Jul 2026).

Full gap table: [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md).
