# Release notes — v1.3.134

## Summary

**Industrial mesh gossip honesty (no simplifications):**

1. **NEW_BLOCK height-ahead ownership gate** — `MSG_NEW_BLOCK` cannot inflate `peer.height` / `peer.head` beyond `local_tip + p2p_max_peer_height_ahead` (same window as status in v1.3.131). Fantasy announces are counted and refused before sync/import steering.
2. **Reuse existing knob** — `p2p_max_peer_height_ahead` / `P2P_MAX_PEER_HEIGHT_AHEAD` now covers both mid-session status and block gossip ownership.

## Changes

- `_handle_new_block` soft gate + early return when over window
- Metrics: `native_new_block_height_cap`, `new_block_height_cap_total`
- `node_version`: `1.3.134-industrial`

## Honesty

- Soft scheduling/ownership bound — **not** solicit-only gossip, not parent/fork-choice proof, not tip proof, not libp2p, not public mainnet
- In-window announces still follow existing hash semantic + import path

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13134_p2p_new_block_height_cap.py -q
```
