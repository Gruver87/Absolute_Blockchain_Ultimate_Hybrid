#!/usr/bin/env python3
"""v1.3.97: native peer cert CN/SAN identity extract."""

from __future__ import annotations

import importlib.util
import sys
import threading
import time
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


def _load_tls_crypto():
    path = ROOT / "scripts" / "p2p_tls_crypto.py"
    spec = importlib.util.spec_from_file_location("p2p_tls_crypto", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_tls = _load_tls_crypto()


def test_needles_v1397():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "peer_cert_identities" in transport
    assert "extract_cert_identities" in transport
    assert "v1.3.97" in transport
    p2p = (ROOT / "network" / "p2p_node.py").read_text(encoding="utf-8")
    assert "peer_cert_identities" in p2p
    assert "_native_peer_identities" in p2p
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "p2p_native_transport" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.97.md").read_text(encoding="utf-8")
    assert "1.3.97-industrial" in notes
    assert "1.3.97" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert hasattr(abs_native.P2PNativeConn, "peer_cert_identities")


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_peer_cert_identities(tmp_path: Path):
    ca_key = tmp_path / "ca.key"
    ca_pem = tmp_path / "ca.pem"
    ca_priv, ca_cert = _tls.generate_ca_material(ca_key, ca_pem)
    a_key = tmp_path / "a.key"
    a_pem = tmp_path / "a.pem"
    b_key = tmp_path / "b.key"
    b_pem = tmp_path / "b.pem"
    _tls.generate_node_material(
        a_key, a_pem, node_cn="node-a", ca_key=ca_priv, ca_cert=ca_cert
    )
    _tls.generate_node_material(
        b_key, b_pem, node_cn="node-b", ca_key=ca_priv, ca_cert=ca_cert
    )

    listener = native.P2PNativeListener(
        "127.0.0.1",
        0,
        1024 * 1024,
        5000,
        str(a_pem),
        str(a_key),
        str(ca_pem),
        True,
    )
    addr = listener.local_addr
    host, port_s = addr.rsplit(":", 1)
    port = int(port_s)
    host = host.strip("[]")
    got = {}

    def server():
        deadline = time.time() + 8.0
        while time.time() < deadline:
            out = listener.accept()
            if out.get("ok") and out.get("conn") is not None:
                c = out["conn"]
                got["ids"] = list(c.peer_cert_identities or [])
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.05)
    conn = native.p2p_native_connect(
        host,
        port,
        1024 * 1024,
        8000,
        cert_path=str(b_pem),
        key_path=str(b_key),
        ca_path=str(ca_pem),
    )
    client_ids = list(conn.peer_cert_identities or [])
    conn.close()
    t.join(timeout=3)
    listener.close()

    assert "node-a" in client_ids
    assert "node-b" in (got.get("ids") or [])


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_native_peer_identities_flag():
    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = False
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._native_peer_identities is True
    assert node.get_p2p_security_status().get("native_peer_identities") is True
