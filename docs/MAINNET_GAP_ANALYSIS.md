# Mainnet Gap Analysis — Industrial Blockchain Readiness

**Project:** Absolute Blockchain Ultimate Hybrid  
**Updated:** 2026-07-04  
**Positioning:** Production-hardened R&D stack → path to public mainnet

This document is the honest engineering checklist after a full repository scan.  
Automated gates (`mainnet_readiness`, `prod_gate`) enforce code-level fail-closed rules; **they do not replace** external audit, validator operations, or legal review.

---

## What is REAL (industrial-grade in-repo)

| Layer | Status | Notes |
|-------|--------|-------|
| L1 blocks, balances, burn, 221M cap | Real | `core/blockchain.py`, `runtime/tokenomics.py` |
| SQLite persistence + WAL prod mode | Real | `storage/database.py`, `sqlite_synchronous=FULL` |
| P2P mesh 2/3/5 nodes | Verified CI | `network/p2p_node.py`, `verify_p2p_ci.py` |
| Native crypto (Rust PyO3) | Real | `native/abs_native`, `ABS_REQUIRE_NATIVE_CRYPTO` |
| State root + P2P import validation | Real | Wave 50–54 |
| EVM subset (Shanghai/Cancun) | Real subset | Not full Ethereum client |
| PoS proposer + slashing | Devnet-proven | Not formal BFT proof |
| NFT marketplace | Prod tier | SQLite-backed |
| Prod config fail-closed | Enforced | `runtime/config.py`, `scripts/prod_gate.py` |

---

## What is DEMO / SIMULATOR (blocked in prod)

| Component | Tier | Prod blocked |
|-----------|------|--------------|
| `bridge/dev_bridge_adapter.py` | dev/test | Yes (`bridge_mode=rust` required) |
| `bridge/mock_l1_rpc.py` | CI only | Not loaded in prod |
| Plasma, Lightning | dev-test | `feature_*=false` |
| WASM VM | r-and-d | Blocked (not real WASM) |
| ZK proofs | r-and-d | Blocked (educational Fiat–Shamir) |
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

## P0 — Blockers before public mainnet

- [ ] Complete all 8 items in `scripts/external_audit_tracker.py`
- [ ] Third-party security audit (L1 + bridge + EVM)
- [ ] Production validator manifest + offline keygen (`scripts/genesis_ceremony_keygen.py`, verify with `--ceremony-dir`)
- [ ] Final `chain_id` (778888) + genesis ceremony hash pinned (`GENESIS_CEREMONY_HASH`)
- [ ] Rotate all secrets (JWT, RPC keys, bridge oracle, L1 RPC)
- [ ] Live prod smoke: `python scripts/mainnet_readiness.py --live`
- [ ] DR drill + incident response runbook
- [ ] Decision: real L1 bridge contracts **or** disable bridge in mainnet v1

---

## P1 — Core strengthening (next engineering waves)

| Area | Action |
|------|--------|
| EVM | Full CREATE2 in block execution; EOF roadmap; opcode parity tests |
| State | Unify `Database` / `ImmutableStateManager` / `StateEngine` |
| Consensus | Single canonical fork-choice + finality path |
| Bridge | On-chain lock/mint contracts + monitored relayer (not proof-only) |
| Storage | Plan beyond SQLite for high-throughput mainnet (or document limits) |
| Tests | E2E prod boot CI, prod P2P mesh, live `prod_smoke` in pipeline |
| Tests | ✅ CI: `industrial_gate.py`, prod boot E2E, `verify_p2p_ci --mode prod-smoke` |

---

## P2 — Post-launch / optional

- Distributed sharding (after stable single-chain mainnet)
- L2 modules remain dev-test unless independently audited
- ZK / PQ only after crypto audit and real implementations

---

## Commands

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

The codebase is a **serious industrial devnet / private testnet** implementation.  
Public mainnet launch requires **organizational gates (audit, ops, genesis)** plus **bridge honesty decision** — not only more Python features.
