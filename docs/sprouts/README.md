# Feature sprouts (ADR 0016)

Industrial L1 is one tip / one apply queue / one mempool / one state-root domain.
Historical modules grow as **profiles**, not as a kitchen-sink on `778888` Rocks.

| Profile | Purpose | Config entry |
|---------|---------|--------------|
| **A — Industrial L1** | Live prod mesh | [`docker/node.prod.mesh*.json`](../../docker/node.prod.mesh1.json) |
| **B — Bridge cutover** | ADR 0010 enablement | [BRIDGE_CUTOVER_PROFILE.md](BRIDGE_CUTOVER_PROFILE.md) |
| **C — App staging** | NFT / app-layer | [APP_STAGING_PROFILE.md](APP_STAGING_PROFILE.md) |
| **D — L2 sandbox** | Plasma / Lightning / WASM aux | [L2_SANDBOX_PROFILE.md](L2_SANDBOX_PROFILE.md) |
| **E — Shard lab** | Separate mesh + DB | [SHARD_LAB_PROFILE.md](SHARD_LAB_PROFILE.md) |

Ops on the core: [CEREMONY_AND_SECRETS.md](CEREMONY_AND_SECRETS.md).
**EVM depth** stays on Profile A (inside apply): [EVM_DEPTH.md](EVM_DEPTH.md).

**Never on forge / L1 trust path:** AI validator/agents, educational ZK/PQ as
consensus crypto, MEV dual-builder, MiniVM beside EVM on the same tip,
in-memory AA without execution bind.

See [ADR 0016](../adr/0016-feature-sprouts-profiles.md).
