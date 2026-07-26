#!/usr/bin/env python3
"""v1.3.158: JWT HS256 secret must be >= 32 bytes."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import middleware.jwt_auth as jwt_mod
from runtime.config import Config


def test_needles_v13158():
    jwt_py = (ROOT / "middleware" / "jwt_auth.py").read_text(encoding="utf-8")
    assert "MIN_HS256_SECRET_BYTES" in jwt_py
    assert "_assert_hs256_secret" in jwt_py
    cfg = (ROOT / "runtime" / "config.py").read_text(encoding="utf-8")
    assert "HS256 requires >= 32 bytes" in cfg
    notes = (ROOT / "RELEASE_NOTES_v1.3.158.md").read_text(encoding="utf-8")
    assert "1.3.158-industrial" in notes
    assert Config().node_version.startswith("1.3.")


def test_generate_token_refuses_short_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "short-secret-only-25-bytes")
    jwt_mod.jwt_auth._dev_fallback = ""
    with pytest.raises(RuntimeError, match="too short for HS256"):
        jwt_mod.jwt_auth.generate_token("0xabc", role="admin")


def test_generate_token_ok_at_32(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    jwt_mod.jwt_auth._dev_fallback = ""
    token = jwt_mod.jwt_auth.generate_token("0xabc", role="admin")
    ok, payload = jwt_mod.jwt_auth.verify_token(token)
    assert ok is True
    assert payload and payload.get("address") == "0xabc"
