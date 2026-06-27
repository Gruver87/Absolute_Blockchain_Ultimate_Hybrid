#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Config: bridge settings from JSON and env."""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config


def test_config_default_bridge_manual_confirm():
    cfg = Config()
    assert cfg.bridge_mode == "rust"
    assert cfg.bridge_auto_confirm_sec == 0


def test_config_loads_bridge_auto_confirm_from_json():
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"bridge_auto_confirm_sec": 45, "bridge_mode": "simulator"}, f)
        cfg = Config.from_json(path)
        assert cfg.bridge_auto_confirm_sec == 45
        assert cfg.bridge_mode == "simulator"
    finally:
        os.remove(path)


def test_config_bridge_auto_confirm_from_env(monkeypatch):
    monkeypatch.setenv("BRIDGE_AUTO_CONFIRM_SEC", "120")
    monkeypatch.setenv("BRIDGE_ENABLED", "false")
    cfg = Config().apply_env()
    assert cfg.bridge_auto_confirm_sec == 120
    assert cfg.bridge_enabled is False
