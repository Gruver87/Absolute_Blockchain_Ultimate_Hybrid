# Release notes — v1.3.98

## Summary

**Native auto-pong keepalive:** on the native read path, `read_message` / `read_messages` can reply to `ping` in-band and omit it from returned messages (`auto_pong=true`). Config: `p2p_native_auto_pong` / `P2P_NATIVE_AUTO_PONG` (default on when native transport is enabled).

## Changes

- `maybe_auto_pong` + `auto_pong` flag on read APIs; `auto_pongs` counter getter
- `PeerConnection.recv` passes auto-pong on native batch/single reads
- Status `native_auto_pong`; metric `abs_p2p_native_auto_pong`
- `node_version`: `1.3.98-industrial`

## Honesty

- Still **not** full Rust message-loop ownership (dispatch / strikes / gossip remain Python)
- Auto-pong is **keepalive only** — not generic handler dispatch / libp2p
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v1398_p2p_native_auto_pong.py -q
```
