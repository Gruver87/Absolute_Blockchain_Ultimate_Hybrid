# Release notes — v1.3.135

## Summary

**Industrial mesh tip ownership + local state_root honesty (no simplifications):**

1. **Local state_root consistency** — when the local header at the probed height is known, peer `state_root` must match (`bad_state_root_response_local_root`). `expected_head` now comes from tip **or** that historical header (not always tip).
2. **Handshake height-ahead** — admission uses the same `p2p_max_peer_height_ahead` window as status/NEW_BLOCK; capped handshakes do not install fantasy `head_hash`.
3. **Status capped ⇒ refuse fantasy head** — when status height is capped, `peer.head` is not updated from the fantasy announce.

## Changes

- `_cap_claimed_peer_height` shared helper
- `_state_root_request_ctx` + waiter local-root check
- Metrics: `native_handshake_height_cap`, `handshake_height_cap_total`, `native_status_capped_head_refuse`, `native_state_root_local_consistency`, `state_root_local_rejects_total`
- `node_version`: `1.3.135-industrial`

## Honesty

- Soft local consistency when header known — **not** merkle/path tip proof, not fork-choice ownership, not libp2p, not ceremony, not public mainnet
- Height cap remains a soft scheduling bound

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13135_p2p_tip_ownership_and_local_root.py -q
```
