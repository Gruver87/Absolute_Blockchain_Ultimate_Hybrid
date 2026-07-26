# Release notes — v1.3.143

## Summary

**Industrial mempool DoS honesty (no simplifications):**

1. **`MSG_NEW_TX` off the sync exempt budget** — gossip hits the primary per-peer rate limit (Python + Rust default exempt set). Sync types (`get_mempool` / `mempool` / blocks / status) stay exempt.
2. **Cheap refuse before expensive validate** — known mempool hashes skip `validate_transaction` / DB.
3. **Signature before state** — when signatures are required or present, ECDSA runs before nonce/balance DB lookups.
4. **No double validate on P2P accept** — `chain_prevalidated` / `signature_preverified` on mempool add after wire build.

## Changes

- `network/p2p_node.py` — RATE_LIMIT_EXEMPT, dup refuse, ingest flags
- `native/abs_native/src/p2p_rate_limit.rs` — remove `new_tx` from DEFAULT_EXEMPT
- `core/blockchain.py` — sig-before-DB order
- `blockchain/mempool.py` — `chain_prevalidated`
- Metrics / security status gauges
- `node_version`: `1.3.143-industrial`

## Honesty / analysis of the three “critical” asks

| Ask | Reality in this release |
|-----|-------------------------|
| Mempool Sybil/DoS | **Partial close** of CPU/admission ordering + primary rate for gossip. **Not** anti-Sybil, not fee-market, not tip-proof. |
| P2P Long-Range / Eclipse | Soft eclipse/subnet + height/head/wire gates already shipped (v1.3.13x–142). Full Long-Range needs weak-subjectivity checkpoints — **not this wave**. |
| RocksDB → full Rust | Engine already Rust (`RocksEngine`). Full store rewrite is multi-release P3 — **not this wave**. |

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13143_mempool_cheap_refuse.py tests/unit/test_v1377_p2p_ingress.py -q
```
