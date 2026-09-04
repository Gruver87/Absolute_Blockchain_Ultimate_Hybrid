# Architecture Decision Records

Boundary ADRs for Absolute Blockchain Ultimate Hybrid.  
**Stack claimed in docs:** **0001–0016** · **0013 intentionally unused** (number reserved / skipped).

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-tip-safety.md) | Tip safety | Accepted |
| [0002](0002-p2p-transport-boundary.md) | P2P transport boundary | Accepted |
| [0003](0003-sync-consistency.md) | Sync consistency / solicit hub | Accepted |
| [0004](0004-catchup-path-a.md) | Catch-up Path A | Accepted |
| [0005](0005-fork-reconcile.md) | Fork reconcile | Accepted |
| [0006](0006-storage-boundary.md) | StoragePort | Accepted |
| [0007](0007-consensus-boundary.md) | ConsensusPort / Round SM | Accepted |
| [0008](0008-hotpath-wire-codec.md) | Hot-path wire codec | Accepted |
| [0009](0009-optional-native-fallback.md) | Optional native fallback | Accepted |
| [0010](0010-evm-bridge-boundary.md) | EVM / BridgePort | Accepted |
| [0011](0011-rpc-api-boundary.md) | QueryFacade / RPC | Accepted |
| [0012](0012-chaos-injection.md) | Chaos injection | Accepted |
| *0013* | *(intentionally unused)* | — |
| [0014](0014-graceful-shutdown-deep-health.md) | Graceful shutdown / deep ready | Accepted |
| [0015](0015-observability-secret-management.md) | Observability + SecretManager | Accepted |
| [0016](0016-feature-sprouts-profiles.md) | Feature sprouts / profiles | Accepted |

System map: [ARCHITECTURE.md](../ARCHITECTURE.md) · sprouts: [sprouts/](../sprouts/)

**R&D ADRs not in this freeze:** [0017–0021](https://github.com/Gruver87/experimental/tree/main/docs/adr) live in [`Gruver87/experimental`](https://github.com/Gruver87/experimental) (Long-Range / rust-libp2p / mempool phases). Hybrid default transport remains TCP+TLS (ADR 0002). `feature_libp2p` / `feature_long_range` stay **false** on prod mesh JSON. Experimental B1 (libp2p 48h) is **PASS** — still not a Hybrid cutover.
