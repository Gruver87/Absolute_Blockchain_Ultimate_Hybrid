#!/usr/bin/env python3
"""v1.3.89: P2P Sybil/Eclipse — public subnet diversity + reserved outbound slots."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import abs_native

from crypto import native
from network.p2p_node import P2PNode
from runtime.config import Config


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_subnet_key_and_public_classification():
    assert native.p2p_subnet_key("203.0.113.10") == "203.0.113.0/24"
    assert native.p2p_ip_is_public("203.0.113.10") is True
    assert native.p2p_ip_is_public("172.18.0.5") is False
    assert native.p2p_ip_is_public("10.0.0.1") is False
    assert native.p2p_ip_is_public("192.168.1.1") is False
    assert native.p2p_ip_is_public("127.0.0.1") is False


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_public_subnet_cap_private_exempt():
    # max_peers=20, per_ip=0, per_subnet=2, reserved=0
    gov = native.P2PConnectionGovernor(20, 0, 2, 0)
    assert gov.allow_inbound(0, "203.0.113.1") is None
    gov.on_connected("203.0.113.1")
    assert gov.allow_inbound(1, "203.0.113.2") is None
    gov.on_connected("203.0.113.2")
    assert gov.allow_inbound(2, "203.0.113.3") == "max_peers_per_subnet"
    assert int(gov.subnet_rejects) >= 1
    # Docker private mesh: same /24 must NOT hit subnet cap
    priv = native.P2PConnectionGovernor(20, 0, 2, 0)
    for i in range(5):
        ip = f"172.18.0.{i + 1}"
        assert priv.allow_inbound(i, ip) is None
        priv.on_connected(ip)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_reserved_outbound_slots():
    # max_peers=5, reserved=2 → inbound cap at 3
    gov = native.P2PConnectionGovernor(5, 0, 0, 2)
    assert gov.reserved_outbound_slots == 2
    assert gov.allow_inbound(3, "203.0.113.9") == "reserved_outbound_slots"
    assert int(gov.reserved_slot_rejects) >= 1
    assert gov.allow_outbound(3) is None
    assert gov.allow_outbound(5) == "max_peers"


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_diversity_snapshot_eclipse_at_risk():
    gov = native.P2PConnectionGovernor(50, 0, 4, 2)
    ips = ["203.0.113.1", "203.0.113.2", "203.0.113.3"]
    snap = gov.diversity_snapshot(ips, 0.34)
    assert snap["public_peers"] == 3
    assert snap["unique_public_subnets"] == 1
    assert snap["eclipse_ratio"] == pytest.approx(1.0)
    assert snap["at_risk"] is True
    assert snap["densest_subnet"] == "203.0.113.0/24"
    # Private-only mesh: not at risk
    priv_ips = ["172.18.0.1", "172.18.0.2", "172.18.0.3"]
    snap2 = gov.diversity_snapshot(priv_ips, 0.34)
    assert snap2["public_peers"] == 0
    assert snap2["at_risk"] is False


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_security_exposes_sybil_fields():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._conn_governor is not None
    assert int(node._conn_governor.max_peers_per_subnet) == int(cfg.p2p_max_peers_per_subnet)
    assert int(node._conn_governor.reserved_outbound_slots) == int(
        cfg.p2p_reserved_outbound_slots
    )
    status = node.get_p2p_security_status()
    assert "max_peers_per_subnet" in status
    assert "reserved_outbound_slots" in status
    assert "eclipse_ratio" in status
    assert "eclipse_at_risk" in status
    assert "unique_public_subnets" in status
    assert status.get("native_conn_governor") is True
