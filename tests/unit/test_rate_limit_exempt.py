#!/usr/bin/env python3
"""Rate limit exemptions for devnet probes and health checks."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.http import _is_rate_limit_exempt


def test_health_paths_exempt():
    assert _is_rate_limit_exempt("/health/live") is True
    assert _is_rate_limit_exempt("/health/ready") is True


def test_devnet_probe_paths_exempt():
    for path in ("/status", "/peers", "/sync/status", "/consensus/stats", "/sync/fast-sync"):
        assert _is_rate_limit_exempt(path) is True


def test_write_paths_not_exempt():
    assert _is_rate_limit_exempt("/transactions") is False
    assert _is_rate_limit_exempt("/tx/send") is False


def test_rate_limit_disabled_when_rpm_zero():
    from api.http import configure_rate_limiter
    from runtime.config import Config

    cfg = Config()
    cfg.rate_limit_rpm = 0
    configure_rate_limiter(cfg)
    import api.http as http_mod
    assert http_mod._RATE_LIMIT_AVAILABLE is False
    assert http_mod._rate_limiter is None
