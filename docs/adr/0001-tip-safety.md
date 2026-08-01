# ADR 0001 — Tip Safety Domain (Stage 1)

- **Status:** Accepted
- **Date:** 2026-07-29
- **Deciders:** Absolute Blockchain maintainers

## Context

The node historically treated tip selection and finality as side effects of
`ConsensusAdapter` event handlers and soft P2P checks. `consensus/reorg_engine.py`
is explicitly legacy/test-only. Production deploy requires a single,
fail-closed tip/finality boundary that is unit-testable without P2P or HTTP.

## Decision

Introduce an isolated domain package `consensus/tip_safety/` with:

| Component | Responsibility |
|-----------|----------------|
| `BlockRef` / errors | Strict validation of height + 32-byte digests |
| `TipState` | Canonical tip + finalized floor (thread-safe snapshots) |
| `ReorgPolicy` | Extend / same-height reorg / reject (unknown parent fail-closed) |
| `ForkChoice` | Deterministic total order: higher height, then higher hash |
| `TipSafetyService` | Evaluate / apply candidates; advance finality |

Stage 1 ships **domain + unit tests only**. No wiring into
`network/p2p_node.py` or `core/blockchain.py`. No prod enforce flag yet.

## Consequences

### Positive

- Tip/finality rules are explicit, typed, and fail-closed.
- Tests cover negative paths (bad hash, finality regress, partition gaps).
- Later stages can adapter-wire without rewriting policy.

### Negative / limits (honest)

- No full DAG ancestry store: deep reorgs and height gaps raise
  `TipUnknownParentError` until a store adapter exists.
- Not BFT / Casper quorum / long-range proof.
- Not enabled on the live commit path in stage 1.

## Non-goals (stage 1)

- libp2p transport rewrite
- Prod `tip_safety_enforce` boot gate
- Shadow metrics on live mesh
- Replacing all consensus engines

## Stage 2 — Shadow mode (2026-07-29)

- Config: `tip_safety_shadow` / env `TIP_SAFETY_SHADOW` (default **off**)
- Observer: `consensus/tip_safety/shadow.py` (`TipSafetyShadowObserver`)
- Wired on `P2PNode.import_block` / `_import_block_async` — **observe only** when enforce off
- Metrics: `abs_tip_safety_shadow_*` via P2P security status

## Stage 3 — Enforce (2026-07-29)

- Config: `tip_safety_enforce` / `TIP_SAFETY_ENFORCE` (default off in Config; **required true in prod**)
- Enforce implies shadow observation
- Policy reject or observer failure → **refuse import** (fail-closed) before chain apply
- `scripts/prod_gate.py` + `Config.validate()` require `tip_safety_enforce` in prod profiles
- Prod JSON examples updated (`docker/node.prod*.json`, `node.prod*.json`, k8s)

Honest limits remaining: bounded tip ``AncestryWindow`` (stage-1.5 / ADR 0016)
is not a full DAG store and not BFT/Long-Range tip proof; height gaps ahead of tip
still require sync fill.
