# Release notes — v1.3.152

## Summary

**Industrial discovery ownership honesty (no simplifications):**

1. **Solicit-only `MSG_PEERS`** — unsolicited peer lists are struck (`unsolicited_peers`) and never dialed / remembered.
2. **Discovery pull-armed** — `_discovery_loop` uses `_wait_peer_response` with `kind=peers`, then `_ingest_discovered_peers`.
3. Config: `p2p_peers_solicit_only` / `P2P_PEERS_SOLICIT_ONLY` (default on).

## Changes

- `network/p2p_node.py` — refuse + ingest helper + discovery wait
- Config / metrics / security status gauges + counters
- `node_version`: `1.3.152-industrial`

## Honesty

- Soft DoS / dial-amplification / eclipse-surface honesty — **not** tip proof, not Long-Range / weak-subjectivity, not anti-Sybil DHT, not libp2p / public mainnet

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13152_peers_solicit_only.py -q
```
