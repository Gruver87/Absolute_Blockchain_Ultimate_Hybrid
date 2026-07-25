# Release notes — v1.3.129

## Summary

**Industrial state-root mesh honesty (no simplifications):**

1. **Outbound `state_root_response` height honesty** — answers for height `H` use tip live root/head only when `H==tip`. Historical heights use that block’s `state_root` + `hash`. Requests ahead of tip or missing incomplete headers are refused (no mislabeled tip payload).
2. **Unsolicited response cannot inflate `peer.height`** — height ownership stays handshake / status / `new_block`. Stops fantasy-height catch-up steering via gossiped state_root probes.

## Changes

- `P2PNode._state_root_response_for_height`
- Counters/metrics: `state_root_outbound_refuse_total`, `native_state_root_outbound_honesty`
- `node_version`: `1.3.129-industrial`

## Honesty

- Still **not** tip existence proof on peers / fork-choice / root-belongs-to-head crypto / libp2p / public mainnet
- Ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13129_p2p_state_root_outbound_honesty.py -q
```
