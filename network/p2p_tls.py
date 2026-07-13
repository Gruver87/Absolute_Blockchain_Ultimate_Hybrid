#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Optional TLS wrappers for P2P TCP (mainnet / public mesh)."""

from __future__ import annotations

import os
import ssl
from typing import Optional, Tuple


def p2p_tls_enabled(config) -> bool:
    return bool(getattr(config, "p2p_tls_enabled", False))


def _resolve_path(config, attr: str) -> str:
    raw = getattr(config, attr, "") or ""
    return os.path.expanduser(str(raw).strip())


def validate_p2p_tls_config(config) -> Tuple[list[str], list[str]]:
    """Return (errors, warnings) for TLS material when enabled."""
    errors: list[str] = []
    warnings: list[str] = []
    if not p2p_tls_enabled(config):
        return errors, warnings
    cert = _resolve_path(config, "p2p_tls_cert_path")
    key = _resolve_path(config, "p2p_tls_key_path")
    ca = _resolve_path(config, "p2p_tls_ca_path")
    if not cert or not os.path.isfile(cert):
        errors.append(f"p2p_tls_cert_path missing: {cert or '(unset)'}")
    if not key or not os.path.isfile(key):
        errors.append(f"p2p_tls_key_path missing: {key or '(unset)'}")
    if bool(getattr(config, "p2p_tls_require_client_cert", False)) and (
        not ca or not os.path.isfile(ca)
    ):
        errors.append(f"p2p_tls_ca_path required for mTLS: {ca or '(unset)'}")
    elif not ca:
        warnings.append("p2p_tls_ca_path unset — outbound peers skip CA verify (dev only)")
    return errors, warnings


def build_p2p_server_ssl_context(config) -> Optional[ssl.SSLContext]:
    if not p2p_tls_enabled(config):
        return None
    errors, _warnings = validate_p2p_tls_config(config)
    if errors:
        return None
    cert = _resolve_path(config, "p2p_tls_cert_path")
    key = _resolve_path(config, "p2p_tls_key_path")
    ca = _resolve_path(config, "p2p_tls_ca_path")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(certfile=cert, keyfile=key)
    if bool(getattr(config, "p2p_tls_require_client_cert", False)):
        if ca and os.path.isfile(ca):
            ctx.load_verify_locations(cafile=ca)
        ctx.verify_mode = ssl.CERT_REQUIRED
    else:
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def build_p2p_client_ssl_context(config) -> Optional[ssl.SSLContext]:
    if not p2p_tls_enabled(config):
        return None
    errors, _warnings = validate_p2p_tls_config(config)
    if errors:
        return None
    cert = _resolve_path(config, "p2p_tls_cert_path")
    key = _resolve_path(config, "p2p_tls_key_path")
    ca = _resolve_path(config, "p2p_tls_ca_path")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    if cert and key and os.path.isfile(cert) and os.path.isfile(key):
        ctx.load_cert_chain(certfile=cert, keyfile=key)
    if ca and os.path.isfile(ca):
        ctx.load_verify_locations(cafile=ca)
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.check_hostname = False
    else:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def p2p_tls_status(config) -> dict:
    enabled = p2p_tls_enabled(config)
    errors, warnings = validate_p2p_tls_config(config) if enabled else ([], [])
    return {
        "enabled": enabled,
        "require_client_cert": bool(getattr(config, "p2p_tls_require_client_cert", False)),
        "cert_configured": bool(_resolve_path(config, "p2p_tls_cert_path")),
        "ca_configured": bool(_resolve_path(config, "p2p_tls_ca_path")),
        "ready": enabled and not errors,
        "errors": errors[:5],
        "warnings": warnings[:5],
    }
