#!/usr/bin/env python3
"""v1.3.91: native rustls TLS on P2PNativeListener/Conn."""

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


_tls_crypto = _load_tls_crypto()
generate_ca_material = _tls_crypto.generate_ca_material
generate_node_material = _tls_crypto.generate_node_material


def test_needles_v1391():
    transport = (ROOT / "native" / "abs_native" / "src" / "p2p_transport.rs").read_text(
        encoding="utf-8"
    )
    assert "rustls" in transport
    assert "p2p_native_tls_available" in transport or "ServerConfig" in transport
    assert "CaOnlyServerVerifier" in transport or "WebPkiClientVerifier" in transport
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    # Live config advances; pin lives in RELEASE_NOTES / CHANGELOG.
    assert "p2p_native_transport" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.91.md").read_text(encoding="utf-8")
    assert "1.3.91-industrial" in notes
    # Live config advances with later waves; pin checked in RELEASE_NOTES.
    assert "1.3.91" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert hasattr(abs_native, "p2p_native_tls_available")
    assert hasattr(native, "p2p_native_tls_available")
    assert native.p2p_native_tls_available() is True


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_native_tls_framed_roundtrip(tmp_path: Path):
    ca_key = tmp_path / "ca.key"
    ca_pem = tmp_path / "ca.pem"
    ca_priv, ca_cert = generate_ca_material(ca_key, ca_pem)
    a_key = tmp_path / "a.key"
    a_pem = tmp_path / "a.pem"
    b_key = tmp_path / "b.key"
    b_pem = tmp_path / "b.pem"
    generate_node_material(a_key, a_pem, node_cn="node-a", ca_key=ca_priv, ca_cert=ca_cert)
    generate_node_material(b_key, b_pem, node_cn="node-b", ca_key=ca_priv, ca_cert=ca_cert)

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
    assert bool(listener.tls) is True
    addr = listener.local_addr
    host, port_s = addr.rsplit(":", 1)
    port = int(port_s)
    host = host.strip("[]")

    def server():
        deadline = time.time() + 8.0
        while time.time() < deadline:
            out = listener.accept()
            if out.get("ok") and out.get("conn") is not None:
                c = out["conn"]
                assert bool(c.tls) is True
                line = c.read_line()
                assert line.get("ok") is True
                assert b"ping" in bytes(line.get("line") or b"")
                c.write(b'{"type":"pong","data":null}\n')
                c.close()
                return

    t = threading.Thread(target=server, daemon=True)
    t.start()
    time.sleep(0.1)
    conn = native.p2p_native_connect(
        host,
        port,
        1024 * 1024,
        8000,
        cert_path=str(b_pem),
        key_path=str(b_key),
        ca_path=str(ca_pem),
    )
    assert bool(conn.tls) is True
    assert len(str(conn.peer_cert_sha256 or "")) == 64
    conn.write(b'{"type":"ping","data":null}\n')
    out = conn.read_line()
    assert out.get("ok") is True, out
    assert b"pong" in bytes(out.get("line") or b"")
    conn.close()
    listener.close()
    t.join(timeout=3)


@pytest.mark.skipif(
    not getattr(native, "native_available", lambda: False)(),
    reason="abs_native required",
)
def test_p2p_node_native_tls_flag_with_valid_paths(tmp_path: Path):
    ca_key = tmp_path / "ca.key"
    ca_pem = tmp_path / "ca.pem"
    ca_priv, ca_cert = generate_ca_material(ca_key, ca_pem)
    n_key = tmp_path / "n.key"
    n_pem = tmp_path / "n.pem"
    generate_node_material(n_key, n_pem, node_cn="node1", ca_key=ca_priv, ca_cert=ca_cert)

    cfg = Config()
    cfg.require_native_crypto = False
    cfg.deployment_mode = "dev"
    cfg.p2p_native_transport = True
    cfg.p2p_tls_enabled = True
    cfg.p2p_tls_cert_path = str(n_pem)
    cfg.p2p_tls_key_path = str(n_key)
    cfg.p2p_tls_ca_path = str(ca_pem)
    cfg.p2p_tls_require_client_cert = True
    node = P2PNode(cfg, MagicMock(), MagicMock())
    assert node._use_native_transport is True
    assert node._native_tls is True
    status = node.get_p2p_security_status()
    assert status.get("native_p2p_transport") is True
    assert status.get("native_p2p_tls") is True
