#!/usr/bin/env python3
"""P2P optional TLS wire encryption tests."""

import os
import ssl
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from network.p2p_tls import (
    build_p2p_client_ssl_context,
    build_p2p_server_ssl_context,
    fingerprint_allowlist,
    handshake_node_id_matches_cert,
    p2p_tls_status,
    validate_p2p_tls_config,
)
from runtime.config import Config


def test_tls_disabled_by_default():
    cfg = Config()
    assert cfg.p2p_tls_enabled is False
    assert build_p2p_server_ssl_context(cfg) is None
    assert build_p2p_client_ssl_context(cfg) is None
    status = p2p_tls_status(cfg)
    assert status["enabled"] is False
    assert status["ready"] is False


def test_tls_enabled_requires_material():
    cfg = Config()
    cfg.p2p_tls_enabled = True
    errors, _warnings = validate_p2p_tls_config(cfg)
    assert errors
    with pytest.raises(RuntimeError, match="P2P TLS server config invalid"):
        build_p2p_server_ssl_context(cfg)
    with pytest.raises(RuntimeError, match="P2P TLS client config invalid"):
        build_p2p_client_ssl_context(cfg)


def test_tls_status_reports_not_ready_when_enabled_without_files():
    cfg = Config()
    cfg.p2p_tls_enabled = True
    status = p2p_tls_status(cfg)
    assert status["enabled"] is True
    assert status["ready"] is False
    assert status["errors"]
    assert status["identity_binding"] == "cn_san_match"
    assert status["server_verify_mode"] == "CERT_REQUIRED"
    assert status["client_verify_mode"] == "CERT_REQUIRED"


def test_handshake_node_id_matches_cert():
    assert handshake_node_id_matches_cert("docker-prod-mesh-1", {"docker-prod-mesh-1"})
    assert not handshake_node_id_matches_cert("evil", {"docker-prod-mesh-1"})
    assert not handshake_node_id_matches_cert("docker-prod-mesh-1", set())


def test_fingerprint_allowlist_from_config():
    cfg = Config()
    cfg.p2p_tls_peer_fingerprints = "AaBb, ccdd"
    assert fingerprint_allowlist(cfg) == {"aabb", "ccdd"}


def test_build_contexts_with_real_mesh_material(tmp_path):
    import importlib.util
    from pathlib import Path

    path = Path(ROOT) / "scripts" / "p2p_tls_crypto.py"
    spec = importlib.util.spec_from_file_location("p2p_tls_crypto", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    dirs = mod.generate_mesh_tls_crypto(
        tmp_path, ["docker-prod-mesh-1", "docker-prod-mesh-2"], force=True
    )
    cfg = Config()
    cfg.p2p_tls_enabled = True
    cfg.p2p_tls_fail_closed = True
    cfg.p2p_tls_require_client_cert = True
    cfg.p2p_tls_cert_path = str(dirs["node1"] / "node.pem")
    cfg.p2p_tls_key_path = str(dirs["node1"] / "node.key")
    cfg.p2p_tls_ca_path = str(tmp_path / "ca.pem")
    server = build_p2p_server_ssl_context(cfg)
    client = build_p2p_client_ssl_context(cfg)
    assert isinstance(server, ssl.SSLContext)
    assert isinstance(client, ssl.SSLContext)
    assert server.verify_mode == ssl.CERT_REQUIRED
    assert client.verify_mode == ssl.CERT_REQUIRED
    status = p2p_tls_status(cfg)
    assert status["ready"] is True
    assert status["fail_closed"] is True
