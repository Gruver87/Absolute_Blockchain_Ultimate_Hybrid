# tests/benchmarks/test_hot_paths.py
"""
ADR 0008 — Hot-path DoD benches (Step A).

Verifies Borsh wire_codec v2 vs legacy data_json on 10k × ~1 KiB packets,
plus Merkle-from-digests and GhostForest select_head without JSON tree dumps.

Skip when abs_native is not installed (CI without maturin wheel).
"""

from __future__ import annotations

import json
import os
import time
from typing import List, Tuple

import pytest

from crypto.native import native_available
from network import wire_codec

pytestmark = pytest.mark.skipif(
    not native_available() or not wire_codec.wire_codec_available(),
    reason="abs_native wire_codec not installed",
)

N_PACKETS = int(os.getenv("ABS_HOTPATH_BENCH_N", "10000"))
PAYLOAD_BODY = 900  # → frame ~1 KiB with envelope overhead
WARMUP = 50


def _make_payload(i: int) -> bytes:
    # Deterministic ~900 B body; remaining frame budget is Borsh headers.
    header = f"idx={i:08d}|".encode("ascii")
    pad = bytes((i + j) % 256 for j in range(PAYLOAD_BODY - len(header)))
    return header + pad


def _build_batch(n: int) -> List[Tuple[str, bytes]]:
    return [("new_tx", _make_payload(i)) for i in range(n)]


def _ns() -> int:
    return time.perf_counter_ns()


def test_wire_codec_version_and_nominal_size():
    assert wire_codec.wire_codec_version() == 2
    assert wire_codec.nominal_packet_bytes() == 1024


def test_wire_v2_roundtrip_1kib_class():
    payload = _make_payload(42)
    frame = wire_codec.encode_wire_v2("new_tx", payload)
    assert len(frame) <= 1100
    assert abs(len(frame) - 1024) < 200  # 1 KiB class
    env = wire_codec.decode_wire_v2(frame)
    assert env["version"] == 2
    assert env["type"] == "new_tx"
    assert env["payload"] == payload


def test_wire_v2_batch_10k_encode_decode_faster_than_legacy_data_json():
    items = _build_batch(N_PACKETS)
    # Warmup
    for _ in range(WARMUP):
        wire_codec.encode_wire_v2("new_tx", items[0][1])

    t0 = _ns()
    frames_v2 = wire_codec.encode_wire_v2_batch(items)
    encode_v2_ns = _ns() - t0
    assert len(frames_v2) == N_PACKETS

    t0 = _ns()
    decoded_v2 = wire_codec.decode_wire_v2_batch(frames_v2)
    decode_v2_ns = _ns() - t0
    assert len(decoded_v2) == N_PACKETS
    assert decoded_v2[0]["payload"] == items[0][1]
    assert decoded_v2[-1]["payload"] == items[-1][1]

    # Legacy: NDJSON line with JSON object wrapping the same body as hex-ish ascii.
    legacy_items = []
    for i, (_t, payload) in enumerate(items):
        # Represent payload as compact JSON object (~same size class).
        data = {
            "i": i,
            "b": payload[:64].hex(),
            "pad": "x" * max(0, PAYLOAD_BODY - 80),
        }
        legacy_items.append(("new_tx", data))

    for _ in range(WARMUP):
        wire_codec.encode_legacy_data_json_line("new_tx", legacy_items[0][1])

    t0 = _ns()
    frames_legacy = [
        wire_codec.encode_legacy_data_json_line(t, d) for t, d in legacy_items
    ]
    encode_legacy_ns = _ns() - t0

    t0 = _ns()
    for line in frames_legacy:
        wire_codec.decode_legacy_data_json_line(line)
    decode_legacy_ns = _ns() - t0

    # Report (visible under pytest -s).
    print(
        f"\n[hotpath] N={N_PACKETS} "
        f"encode_v2={encode_v2_ns/1e6:.2f}ms decode_v2={decode_v2_ns/1e6:.2f}ms "
        f"encode_legacy={encode_legacy_ns/1e6:.2f}ms decode_legacy={decode_legacy_ns/1e6:.2f}ms"
    )

    # DoD: Borsh path must beat legacy NDJSON on encode+decode wall time.
    assert encode_v2_ns + decode_v2_ns < encode_legacy_ns + decode_legacy_ns


def test_merkle_root_from_digests_nogil_path():
    import abs_native as n  # type: ignore

    leaves = [os.urandom(32) for _ in range(1024)]
    root = n.merkle_root_from_digests(leaves)
    assert isinstance(root, (bytes, bytearray))
    assert len(root) == 32
    # Deterministic
    assert bytes(n.merkle_root_from_digests(leaves)) == bytes(root)


def test_ghostforest_select_head_no_json_dump():
    forest = wire_codec.create_ghost_forest()
    forest.insert_block("genesis", None, 0, 1)
    forest.insert_block("a1", "genesis", 1, 10)
    forest.insert_block("b1", "genesis", 1, 5)
    forest.insert_block("a2", "a1", 2, 10)
    head = forest.select_head()
    assert head == "a2"
    assert forest.cumulative_weight("genesis") >= 26
    assert forest.len() >= 4


def test_wire_v2_frames_smaller_and_roundtrip_stable():
    """DoD size/correctness: Borsh frames stay in 1 KiB class and round-trip."""
    n = min(N_PACKETS, 5000)
    items = _build_batch(n)
    frames = wire_codec.encode_wire_v2_batch(items)
    decoded = wire_codec.decode_wire_v2_batch(frames)

    legacy_sizes = []
    for i, (_t, payload) in enumerate(items):
        line = wire_codec.encode_legacy_data_json_line(
            "new_tx",
            {"i": i, "b": payload[:64].hex(), "pad": "x" * max(0, PAYLOAD_BODY - 80)},
        )
        legacy_sizes.append(len(line))

    avg_v2 = sum(len(f) for f in frames) / len(frames)
    avg_legacy = sum(legacy_sizes) / len(legacy_sizes)
    print(f"\n[hotpath] avg_frame_v2={avg_v2:.1f}B avg_legacy={avg_legacy:.1f}B")

    assert len(decoded) == n
    assert decoded[0]["payload"] == items[0][1]
    assert decoded[-1]["payload"] == items[-1][1]
    assert avg_v2 <= 1100
    # Binary envelope should not exceed the NDJSON baseline on average.
    assert avg_v2 < avg_legacy
