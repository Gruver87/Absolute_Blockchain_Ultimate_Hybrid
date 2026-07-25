# Release notes — v1.3.131

## Summary

**Industrial mesh DoS / integrity hardening (no simplifications):**

1. **Solicit-only mempool** — `MSG_MEMPOOL` is fulfilled only for an active `get_mempool` waiter (`request_ctx.kind=mempool`). Unsolicited batches are struck (`unsolicited_mempool`) and never ingested. Gossip remains `MSG_NEW_TX`.
2. **Status height ahead cap** — `peer.height` from mid-session status cannot jump more than `p2p_max_peer_height_ahead` (default 100_000) above local tip. Stops fantasy-height catch-up DoS while allowing real catch-up in windows.

## Changes

- `_sync_mempool_with_peer` + waiter / unsolicited handler
- Config: `p2p_max_peer_height_ahead` / `P2P_MAX_PEER_HEIGHT_AHEAD`
- Metrics: `unsolicited_mempool_rejects_total`, `status_height_cap_total`, `native_mempool_solicit_only`
- `node_version`: `1.3.131-industrial`

## Honesty

- Still **not** tip proof / fork-choice / libp2p / anti-Sybil / external audit / public mainnet
- Cap is a soft scheduling bound, not a height↔hash proof

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13131_p2p_mempool_solicit_and_height_cap.py -q
```
