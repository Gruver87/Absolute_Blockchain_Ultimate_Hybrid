# ADR 0008 — Hot-Path ABI & Wire Codec (Borsh v2)

- **Status:** Accepted A (wire codec + typed batch surface shipping)
- **Date:** 2026-07-30
- **Deciders:** Absolute Blockchain maintainers

## Context

ECDSA / Merkle / GHOST kernels already live in `abs_native`, but the ABI is
JSON strings (`data_json`, `json.dumps(tree)`). That dominates py-spy under
flood and blocks GIL around marshalling rather than crypto.

## Decision

1. **Wire codec v2 (Borsh):** binary line `AB2:` + hex(Borsh `{version=2, msg_type, payload}`)
   replaces NDJSON `data_json` for hot P2P packets (~1 KiB class). Dual-stack
   with v1 JSON remains for interop; inbound **auto-detects** codec.
2. **Peer-aware auto reply:** `P2PNativeConn.peer_wire_codec` is learned from each
   inbound frame; `write_message(..., codec="auto")` and handshake_ack reply in
   the peer's native format without manual config. Policy
   `ABS_P2P_WIRE_CODEC=auto|v1|v2` (default **auto**).
3. **Typed batch ABI:** `merkle_root_from_digests`, `verify_secp256k1_sha256_batch`
   under `py.allow_threads`, and opaque `GhostForest` handle — no per-call
   `json.dumps` of the fork tree.
4. **Python edge:** `network/wire_codec.py` + `NativeTransportAdapter` +
   `PeerConnection._note_peer_wire_codec`; tip_safety / p2p_dispatch see the same
   `(msg_type, data)` after admit for both codecs.

## Honesty

- Lab bench ≠ public mainnet TPS
- v2 codec ≠ full Rust TCP ownership
- GhostForest handle ≠ tip proof / Long-Range

## Definition of Done (A)

- Borsh encode/decode round-trip for 1 KiB × 10k faster than legacy `data_json`
- Benchmark module `tests/benchmarks/test_hot_paths.py`
- industrial / unit needles for `wire_codec_v2` / `GhostForest`
