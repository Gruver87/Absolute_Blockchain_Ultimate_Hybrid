#!/usr/bin/env python3
"""v1.3.128: discovery dialability + handshake/status soft height↔head binding."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crypto import native


DIGEST = "aa" * 32


def test_needles_v13128():
    ingress = (ROOT / "native" / "abs_native" / "src" / "p2p_ingress.rs").read_text(
        encoding="utf-8"
    )
    assert "p2p_peer_addr_is_dialable_inner" in ingress
    wire = (ROOT / "native" / "abs_native" / "src" / "p2p_wire.rs").read_text(
        encoding="utf-8"
    )
    assert "verify_status_height_head_binding_inner" in wire
    assert "verify_handshake_head_semantics_inner" in wire
    assert "bad_status_height_head" in wire
    assert "bad_handshake_height_head" in wire
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "p2p_peer_addr_is_dialable" in p2p
    assert "p2p_discovery_allow_private" in p2p
    assert "verify_p2p_handshake_head_semantics" in p2p
    assert "verify_p2p_status_height_head_binding" in p2p
    notes = (ROOT / "RELEASE_NOTES_v1.3.128.md").read_text(encoding="utf-8")
    assert "1.3.128-industrial" in notes
    # Live Config().node_version advances with later waves; pin notes not config.
    assert "p2p_discovery_allow_private" in (
        ROOT / "runtime" / "config.py"
    ).read_text(encoding="utf-8")
    metrics = (ROOT / "observability" / "metrics.py").read_text(encoding="utf-8")
    assert "abs_p2p_native_discovery_dialability_gate" in metrics
    assert "abs_p2p_native_handshake_head_semantic_gate" in metrics
    assert "abs_p2p_native_status_height_head_gate" in metrics


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_dialability_public_ok_private_blocked():
    assert native.p2p_peer_addr_is_dialable("203.0.113.10:5000", allow_private=False)
    assert not native.p2p_peer_addr_is_dialable("10.0.0.5:5000", allow_private=False)
    assert not native.p2p_peer_addr_is_dialable("127.0.0.1:5000", allow_private=False)
    assert native.p2p_peer_addr_is_dialable("10.0.0.5:5000", allow_private=True)
    assert native.p2p_peer_addr_is_dialable("node1:5000", allow_private=False)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_status_height_requires_digest_head():
    assert (
        native.verify_p2p_status_height_head_binding(
            {"height": 0, "head_hash": ""}
        )
        is None
    )
    assert (
        native.verify_p2p_status_height_head_binding(
            {"height": 3, "head_hash": DIGEST}
        )
        is None
    )
    assert (
        native.verify_p2p_status_height_head_binding({"height": 3, "head_hash": ""})
        == "bad_status_height_head"
    )


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_handshake_height_requires_digest_head():
    good0 = {
        "chain_id": 1,
        "height": 0,
        "head_hash": "",
        "node_id": "n1",
        "p2p_port": 5000,
    }
    assert native.verify_p2p_handshake_head_semantics(good0) is None
    bad = {
        "chain_id": 1,
        "height": 5,
        "head_hash": "",
        "node_id": "n1",
        "p2p_port": 5000,
    }
    assert (
        native.verify_p2p_handshake_head_semantics(bad) == "bad_handshake_height_head"
    )
    good = dict(bad)
    good["head_hash"] = DIGEST
    assert native.verify_p2p_handshake_head_semantics(good) is None
