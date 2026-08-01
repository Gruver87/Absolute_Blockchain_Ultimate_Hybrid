# docs/adr/0016-feature-sprouts-profiles.md
# ADR 0016 — Feature Sprouts & Deployment Profiles

- **Status:** Accepted
- **Date:** 2026-08-01
- **Deciders:** Absolute Blockchain maintainers

## Context

Historical modules (NFT, MiniVM, WASM, Plasma, Lightning, ZK, PQ, sharding,
AI, MEV, smart accounts) shipped behind `FEATURE_*` with dataclass defaults
often `True` for local dig. The industrial L1 core (ADR **0001–0015**) is a
single tip, single `StoragePort`, single apply queue, single mempool, and
strict state-root domain. Turning every feature on that tip collides:

- Sharding mutates L1 balances outside forge / cross-shard gossip steals P2P QoS
- Parallel VMs (EVM + MiniVM + WASM) share gas / mempool / apply backpressure
- Educational ZK/PQ / AI validators paint false trust on TxPipeline / forge
- Aux L2 R&D (Plasma/Lightning) can pollute `/health` honesty if not profiled

Prod already fail-closes `FEATURE_*` via `Config.validate()` and mesh JSON
(`778888`). Missing: an explicit **sprout law** and named profiles so growth
is additive without kitchen-sink on prod Rocks volumes.

## Decision

1. **Industrial L1 core (Profile A)** — `chain_id=778888` prod mesh JSON:
   all `feature_*=false`, `bridge_enabled=false`, `allow_state_root_rewrite=false`,
   `consensus_mode=unified`. Grow only tip-safety, P2P/sync, Rocks, EVM subset
   inside the existing apply path, ceremony/secrets/metrics.

2. **Sprout invariant** — canonical state mutations only via
   `ChainApplyQueue` / Storage UoW. Transport never touches raw Rocks without a
   port. New gossip types are off the prod allowlist or live on a separate mesh.

3. **Profiles (not one kitchen-sink process):**
   - **A — Industrial L1:** Profile A above (live mesh).
   - **B — Bridge cutover:** ADR 0010; `bridge_enabled` only with rust + L1
     proof after contracts; may run beside A but validators may keep bridge OFF.
   - **C — App staging:** NFT (and future app-layer) on `chain_id ≠ 778888`
     or dedicated staging compose; fees/balances through the same UoW.
   - **D — L2 sandbox:** Plasma / Lightning / WASM on **aux DB only**; core
     `/health/ready` independent of sandbox green.
   - **E — Shard lab:** separate compose project, volumes, P2P ports; never
     toggle `FEATURE_SHARDING` onto `778888` Rocks.

4. **Permanently out of forge / L1 trust path:** AI validator/agents,
   educational ZK/PQ as consensus crypto, MEV dual-builder until BlockBuilder
   is the sole forge, in-memory AA/multisig without execution bind, MiniVM
   beside EVM on the same tip.

5. **Honesty** — `features.MODULE_TIERS` must not label prod-blocked modules
   as `"production"`. Evidence Matrix rows for sprouts state proven vs not.

6. **Gates** — `industrial_gate` rejects any `feature_*=true` on prod mesh /
   industrial prod JSON (except documented non-mesh cutover examples that are
   not named `mesh`). Unit tests freeze mesh JSON feature flags.

## Honesty

- This ADR does **not** claim public mainnet or that NFT/L2/shards are ready.
- Bridge OFF remains a valid production posture (ADR 0010).
- Bounded tip ancestry (stage-1.5 window) ≠ Long-Range / BFT quorum proof.

## Definition of Done

- This ADR present; industrial_gate needles for ADR 0016 + mesh FEATURE freeze
- `MODULE_TIERS` / `AT_A_GLANCE` / `ARCHITECTURE` reference 0001–0016
- Profile docs under `docs/sprouts/` for App / Sandbox / Shard / Bridge
- `tests/unit/test_prod_mesh_feature_freeze.py` green
