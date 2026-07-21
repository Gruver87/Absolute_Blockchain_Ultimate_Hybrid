#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты rate limit factory (memory + Redis mock)."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from middleware.rate_limit import RateLimiter, create_rate_limiter


def test_create_rate_limiter_memory_fallback():
    rl = create_rate_limiter(redis_enabled=False, requests_per_minute=5)
    assert isinstance(rl, RateLimiter)
    ok, _ = rl.allow_request("1.2.3.4")
    assert ok is True


def test_create_rate_limiter_redis_when_available():
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.incr.side_effect = [1, 2, 3, 4, 5, 6]
    mock_client.expire.return_value = True

    mock_redis_mod = MagicMock()
    mock_redis_mod.from_url.return_value = mock_client

    with patch.dict(sys.modules, {"redis": mock_redis_mod}):
        from middleware.redis_rate_limit import RedisRateLimiter

        rl = RedisRateLimiter("redis://localhost:6379/0", requests_per_minute=5)
        for i in range(5):
            ok, remaining = rl.allow_request("client-a")
            assert ok is True
        ok, remaining = rl.allow_request("client-a")
        assert ok is False
        assert remaining == 0


def test_create_rate_limiter_redis_unavailable_falls_back():
    with patch("middleware.redis_rate_limit.try_create_redis_limiter", return_value=None):
        rl = create_rate_limiter(
            redis_url="redis://bad:6379/0",
            redis_enabled=True,
            requests_per_minute=10,
            fail_closed=False,
        )
    assert isinstance(rl, RateLimiter)


def test_create_rate_limiter_redis_unavailable_fail_closed():
    with patch("middleware.redis_rate_limit.try_create_redis_limiter", return_value=None):
        rl = create_rate_limiter(
            redis_url="redis://bad:6379/0",
            redis_enabled=True,
            requests_per_minute=10,
            fail_closed=True,
        )
    assert rl is None


def test_redis_incr_fail_closed_denies():
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.incr.side_effect = RuntimeError("redis down")
    mock_redis_mod = MagicMock()
    mock_redis_mod.from_url.return_value = mock_client
    with patch.dict(sys.modules, {"redis": mock_redis_mod}):
        from middleware.redis_rate_limit import RedisRateLimiter

        rl = RedisRateLimiter("redis://localhost:6379/0", fail_closed=True)
        ok, remaining = rl.allow_request("client-x")
        assert ok is False
        assert remaining == 0


def test_jwt_secret_follows_env_after_import(monkeypatch):
    import importlib
    import middleware.jwt_auth as jwt_mod

    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("DEPLOYMENT_MODE", "dev")
    importlib.reload(jwt_mod)
    monkeypatch.setenv("JWT_SECRET", "post-import-secret-key-32chars!!")
    token = jwt_mod.jwt_auth.generate_token("0xabc", role="admin")
    ok, payload = jwt_mod.jwt_auth.verify_token(token)
    assert ok and payload["role"] == "admin"
