# Release notes — v1.3.145

## Summary

**Industrial P2P peer-quality honesty (no simplifications):**

1. **Peer health score includes strikes + import fails** — eclipse prune / score-evict prefer abusive peers, not only height gap / last-seen.
2. **Failed block imports attributed to the sourcing peer** (`quality_import_fails`) on gossip accept and catch-up sync paths.
3. Topology exposes `import_fails` alongside `score` / `strikes`.

## Changes

- `network/p2p_node.py` — `_peer_health_score` penalties, `_score_peer`, `_note_peer_import_fail`
- Metrics: `native_peer_score_quality`
- `node_version`: `1.3.145-industrial`

## Honesty

- Soft scoring for prune/evict — **not** tip proof, not hard peer isolation / ASN diversity, not Long-Range checkpoint, not libp2p / public mainnet

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13145_peer_score_quality.py tests/unit/test_p2p_industrial.py::test_peer_health_score_helper -q
```
