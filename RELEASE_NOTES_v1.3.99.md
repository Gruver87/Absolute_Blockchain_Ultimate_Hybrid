# Release notes — v1.3.99

## Summary

**Native keepalive consume:** under `auto_pong`, the read path also silently consumes inbound `pong` frames and reports `keepalive_touches`. Empty batches that only saw keepalive traffic return a synthetic pong in Python so `last_seen` still updates (fix for ping-only peers).

## Changes

- `maybe_auto_pong` consumes inbound `pong`; counters `auto_keeps` / `keepalive_touches`
- `read_message` / `read_messages` return `keepalive_touches`; timeout-after-keeps → synthetic pong
- Python `recv` empty-batch touch path; status `native_keepalive`; metric `abs_p2p_native_keepalive`
- `node_version`: `1.3.99-industrial`

## Honesty

- Still **not** full Rust message-loop ownership (dispatch / strikes / gossip remain Python)
- Still not libp2p / multiplex
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1399_p2p_native_keepalive.py -q
```
