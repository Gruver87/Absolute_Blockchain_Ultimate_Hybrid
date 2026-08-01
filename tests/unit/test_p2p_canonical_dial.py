# tests/unit/test_p2p_canonical_dial.py
"""Canonical dial ownership: dual-dial must keep one live peer registration."""

from __future__ import annotations

import time

from network.peer_manager import (
    PeerManager,
    PeerManagerSettings,
    preferred_inbound_for,
)


class FakePeer:
    def __init__(self, peer_id: str, *, inbound: bool = False, host: str = "10.0.0.1"):
        self.peer_id = peer_id
        self.host = host
        self.port = 5000
        self.listen_port = 5000
        self.height = 0
        self.head = ""
        self.connected_at = time.time()
        self.last_seen = time.time()
        self.quality_import_fails = 0
        self.closed = False
        self._inbound = inbound

    def close(self) -> None:
        self.closed = True


def _mgr() -> PeerManager:
    return PeerManager(PeerManagerSettings(max_peers=8, peer_timeout=30.0))


def test_preferred_inbound_lexicographic():
    assert preferred_inbound_for("a", "b") is False  # a owns outbound
    assert preferred_inbound_for("b", "a") is True  # b owns inbound
    assert preferred_inbound_for("x", "x") is None
    assert preferred_inbound_for("", "a") is None


def test_canonical_outbound_replaces_noncanonical_inbound():
    """Local 'mesh-1' < remote 'mesh-2' → keep outbound, replace inbound."""
    pm = _mgr()
    inbound = FakePeer("mesh-2", inbound=True, host="10.0.0.2")
    assert pm.register(inbound, inbound=True, local_node_id="mesh-1").allowed
    outbound = FakePeer("mesh-2", inbound=False, host="10.0.0.2")
    decision = pm.register(outbound, inbound=False, local_node_id="mesh-1")
    assert decision.allowed is True
    assert decision.replaced is True
    assert inbound.closed is True
    assert pm.get("mesh-2") is outbound
    assert outbound._inbound is False


def test_noncanonical_outbound_refused_when_canonical_inbound_live():
    """Local 'mesh-2' > remote 'mesh-1' → keep inbound; refuse outbound challenger."""
    pm = _mgr()
    inbound = FakePeer("mesh-1", inbound=True, host="10.0.0.1")
    assert pm.register(inbound, inbound=True, local_node_id="mesh-2").allowed
    outbound = FakePeer("mesh-1", inbound=False, host="10.0.0.1")
    decision = pm.register(outbound, inbound=False, local_node_id="mesh-2")
    assert decision.allowed is False
    assert decision.reason == "duplicate_noncanonical"
    assert outbound.closed is False  # caller closes
    assert inbound.closed is False
    assert pm.get("mesh-1") is inbound


def test_unregister_expected_protects_replacement():
    pm = _mgr()
    old = FakePeer("mesh-2", inbound=True)
    new = FakePeer("mesh-2", inbound=False)
    pm.register(old, inbound=True, local_node_id="mesh-1")
    pm.register(new, inbound=False, local_node_id="mesh-1")
    assert pm.unregister("mesh-2", expected=old) is None
    assert pm.get("mesh-2") is new


def test_higher_id_skips_outbound_register_semantics():
    """Document ownership: mesh-2 must not keep outbound toward mesh-1."""
    from network.peer_manager import preferred_inbound_for

    assert preferred_inbound_for("docker-prod-mesh-2", "docker-prod-mesh-1") is True
    assert preferred_inbound_for("docker-prod-mesh-1", "docker-prod-mesh-2") is False

