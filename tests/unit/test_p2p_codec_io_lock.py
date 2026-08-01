"""Codec lookup must not race native conn IO borrows during egress prepare."""

from __future__ import annotations

from network.p2p_node import PeerConnection


def test_effective_wire_codec_does_not_touch_native_conn():
    peer = PeerConnection(None, None)
    peer._wire_codec = None

    class _Boom:
        @property
        def peer_wire_codec(self):
            raise AssertionError("must not read native conn codec off the IO lock")

    peer._native_conn = _Boom()
    codec = peer._effective_wire_codec()
    assert codec in ("v1", "v2")


def test_note_peer_wire_codec_uses_io_lock():
    peer = PeerConnection(None, None)
    calls = []

    class _Conn:
        def set_peer_wire_codec(self, raw):
            calls.append(raw)

    peer._native_conn = _Conn()
    peer._note_peer_wire_codec("v2")
    assert peer._wire_codec == "v2"
    assert calls == ["v2"]
