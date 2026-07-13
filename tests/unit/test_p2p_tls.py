#!/usr/bin/env python3
"""P2P optional TLS wire encryption tests."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from network.p2p_tls import (
    build_p2p_client_ssl_context,
    build_p2p_server_ssl_context,
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
    assert build_p2p_server_ssl_context(cfg) is None


def test_tls_status_reports_not_ready_when_enabled_without_files():
    cfg = Config()
    cfg.p2p_tls_enabled = True
    status = p2p_tls_status(cfg)
    assert status["enabled"] is True
    assert status["ready"] is False
    assert status["errors"]
