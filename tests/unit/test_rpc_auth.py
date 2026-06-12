#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты RPC API key auth."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from middleware.rpc_auth import RPCApiKeyAuth
from runtime.config import Config


class _FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, super().get(key.lower(), default))


def test_rpc_auth_disabled_by_default():
    auth = RPCApiKeyAuth(required=False, keys=["secret"])
    ok, err = auth.verify(_FakeHeaders())
    assert ok is True
    assert err == ""


def test_rpc_auth_required_valid_key():
    auth = RPCApiKeyAuth(required=True, keys=["key-alpha"])
    ok, _ = auth.verify(_FakeHeaders({"X-API-Key": "key-alpha"}))
    assert ok is True
    ok, err = auth.verify(_FakeHeaders({"Authorization": "Bearer key-alpha"}))
    assert ok is True
    ok, err = auth.verify(_FakeHeaders())
    assert ok is False
    assert "Missing" in err


def test_rpc_auth_invalid_key():
    auth = RPCApiKeyAuth(required=True, keys=["good"])
    ok, err = auth.verify(_FakeHeaders({"X-API-Key": "bad"}))
    assert ok is False
    assert "Invalid" in err


def test_config_prod_requires_rpc_keys(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "prod")
    monkeypatch.setenv("DATA_DIR", "data")
    cfg = Config()
    cfg.apply_env()
    errors = cfg.validate()
    assert any("RPC_API_KEYS" in e for e in errors)
