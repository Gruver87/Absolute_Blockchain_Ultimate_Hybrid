#!/usr/bin/env python3
"""Industrial P2P hardening: wire limits, topology scores, auto prod-mesh detect."""

import asyncio
import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from network.p2p_node import DEFAULT_MAX_P2P_LINE_BYTES, PeerConnection, _max_p2p_line_bytes
from runtime.config import Config


class _FakeReader:
    def __init__(self, payload: bytes):
        self._payload = payload

    async def readline(self):
        return self._payload


class _FakeWriter:
    def get_extra_info(self, key, default=None):
        if key == "peername":
            return ("127.0.0.1", 5001)
        return default

    def write(self, _data):
        pass

    async def drain(self):
        pass

    def close(self):
        pass


@pytest.mark.asyncio
async def test_recv_rejects_oversized_line():
    peer = PeerConnection(_FakeReader(b"x" * 5000), _FakeWriter())
    cfg = Config()
    cfg.p2p_max_message_bytes = 1024
    msg = await peer.recv(cfg)
    assert msg is None


@pytest.mark.asyncio
async def test_recv_accepts_valid_json_line():
    payload = json.dumps({"type": "ping", "data": {}}).encode() + b"\n"
    peer = PeerConnection(_FakeReader(payload), _FakeWriter())
    msg = await peer.recv(Config())
    assert msg is not None
    assert msg["type"] == "ping"


def test_max_p2p_line_bytes_clamps_config():
    cfg = Config()
    cfg.p2p_max_message_bytes = 100
    assert _max_p2p_line_bytes(cfg) == 4096
    cfg.p2p_max_message_bytes = 999999999
    assert _max_p2p_line_bytes(cfg) == 16 * 1024 * 1024
    assert _max_p2p_line_bytes(Config()) == DEFAULT_MAX_P2P_LINE_BYTES


def test_verify_p2p_auto_detects_prod_mesh(monkeypatch):
    path = os.path.join(ROOT, "scripts", "verify_p2p_ci.py")
    spec = importlib.util.spec_from_file_location("verify_p2p_ci", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    calls = []

    def fake_probe(url):
        calls.append(url)
        return url in (
            mod.PROD_MESH_URL1,
            mod.PROD_MESH_URL2,
            mod.PROD_MESH_URL3,
        )

    monkeypatch.setattr(mod, "_probe_health", fake_probe)
    monkeypatch.setattr(
        mod,
        "verify_triple",
        lambda *a, **k: 0,
    )
    monkeypatch.setattr(
        mod,
        "verify_prod_consensus_mesh3",
        lambda *a, **k: 0,
    )
    monkeypatch.setattr(
        mod,
        "verify_prod_post_checks",
        lambda *a, **k: 0,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["verify_p2p_ci.py", "--mode", "auto"],
    )
    rc = mod.main()
    assert rc == 0
    assert mod.PROD_MESH_URL1 in calls
