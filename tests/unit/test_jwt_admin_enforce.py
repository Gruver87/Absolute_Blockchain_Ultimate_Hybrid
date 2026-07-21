#!/usr/bin/env python3
"""JWT admin role enforcement + RPC constant-time key compare."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

os.environ["JWT_SECRET"] = "unit-test-jwt-secret-key-32chars!!"
os.environ.pop("DEPLOYMENT_MODE", None)

import importlib
import middleware.jwt_auth as jwt_mod

importlib.reload(jwt_mod)
jwt_mod.jwt_auth.secret_key = os.environ["JWT_SECRET"]

from middleware.rpc_auth import RPCApiKeyAuth


def test_admin_role_required():
    admin = jwt_mod.jwt_auth.generate_token("0xadmin", role="admin")
    user = jwt_mod.jwt_auth.generate_token("0xuser", role="user")
    ok, payload, err = jwt_mod.jwt_auth.require_role(admin, role="admin")
    assert ok and payload and payload["role"] == "admin"
    ok2, payload2, err2 = jwt_mod.jwt_auth.require_role(user, role="admin")
    assert not ok2
    assert payload2 is not None
    assert "insufficient" in err2


def test_verify_rejects_garbage():
    ok, payload = jwt_mod.jwt_auth.verify_token("not.a.jwt")
    assert ok is False
    assert payload is None


def test_rpc_key_constant_time_accept_reject():
    auth = RPCApiKeyAuth(keys=["good-key-aaaaaaaa", "good-key-bbbbbbbb"], required=True)
    ok, _ = auth.verify({"X-API-Key": "good-key-aaaaaaaa"})
    assert ok
    bad, msg = auth.verify({"X-API-Key": "wrong-key-cccccccc"})
    assert bad is False
    assert "Invalid" in msg


def test_rpc_key_dedupes():
    auth = RPCApiKeyAuth(keys=["same", "same", "other"], required=True)
    assert len(auth._keys) == 2
