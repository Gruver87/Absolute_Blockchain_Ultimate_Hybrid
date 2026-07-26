# Release notes — v1.3.156

## Summary

**Industrial NEW_BLOCK tip-meta honesty (no simplifications):**

1. **Defer tip mutate** — parse `Block.from_dict` before updating `peer.height` / `peer.head` (no tip inflation on bad body).
2. **Announce↔body bind** — claimed announce hash/height must match parsed body (`new_block_announce_hash_mismatch` / `new_block_announce_height_mismatch`).
3. Sequel to v1.3.153 (local known-head bind) + v1.3.155 (status/handshake bind).

## Changes

- `network/p2p_node.py` — parse + body bind before tip mutate
- Config: `p2p_new_block_announce_body_bind` / `P2P_NEW_BLOCK_ANNOUNCE_BODY_BIND` (default on)
- Metrics / security status gauges + refuse counter
- `node_version`: `1.3.156-industrial`

## Honesty

- Soft scheduling / announce body bind — **not** tip existence proof, not root-belongs-to-head merkle, not Long-Range / weak-subjectivity checkpoint, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
.\scripts\check_all.ps1 -Mode Standard
python -m pytest tests/unit/test_v13156_new_block_announce_body_bind.py -q
```
