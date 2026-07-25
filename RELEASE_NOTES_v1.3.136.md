# Release notes — v1.3.136

## Summary

**Industrial consensus-gossip honesty (no simplifications):**

1. **Attestation slot-ahead gate** — after shape + signature checks, `MSG_ATTESTATION` is refused when `slot` or `target_height` exceeds `local_tip_or_slot + p2p_max_attestation_slot_ahead` (default 100_000). Far-ahead votes do not enter LMD and are not relayed.
2. **Config** — `p2p_max_attestation_slot_ahead` / `P2P_MAX_ATTESTATION_SLOT_AHEAD` (falls back to `p2p_max_peer_height_ahead` if unset/0).

## Changes

- `_attestation_ahead_reject_reason` / `_local_attestation_anchor` in `_handle_attestation`
- Strikes: `attestation_slot_ahead`, `attestation_height_ahead`
- Metrics: `native_attestation_slot_ahead`, `attestation_slot_ahead_rejects_total`
- `node_version`: `1.3.136-industrial`

## Honesty

- Soft relative window vs **local** tip/slot — **not** attestation↔canonical-head crypto binding, not tip proof, not full fork-choice ownership, not libp2p, not ceremony / external audit / public mainnet

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13136_p2p_attestation_slot_ahead.py -q
```
