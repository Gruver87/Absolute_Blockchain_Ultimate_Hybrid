#!/usr/bin/env python3
"""v1.3.28 honesty: mining/status, WS/P2P send, API missing, clone, SQLite decode."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_eth_mining_prod_without_p2p_false():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert 'mode in ("prod", "production", "staging")' in http_py
    assert 'if not bool(getattr(p2p, "_running", False))' in http_py


def test_status_degraded_without_sync_engine_when_peers():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert "peer_count > 0 and not sync_engine_bound" in http_py
    assert '"subsystems"' in http_py


def test_api_missing_error_keys():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert "smart_accounts_missing" in http_py
    assert "sync_engine_missing" in http_py
    assert "contract_manager_missing" in http_py


def test_ws_broadcast_counts_send_failures():
    from network.websocket import WebSocketServer

    ws = WebSocketServer()

    class _BadWs:
        async def send(self, _data):
            raise RuntimeError("broadcast failed")

    ws._clients.add(_BadWs())
    asyncio.run(ws._broadcast({"type": "event"}))
    assert ws._send_failures == 1
    assert ws.get_stats()["send_failures"] == 1


def test_message_handler_send_fail_closed():
    from network.p2p.message_handler import MessageHandler

    h = MessageHandler(None, None, None, None, None)
    assert h._send("peer", {"type": "ping"}) is False
    assert h._send_unbound == 1

    class _Boom:
        def send(self, *_a, **_k):
            raise RuntimeError("boom")

    h2 = MessageHandler(None, _Boom(), None, None, None)
    assert h2._send("peer", {"type": "ping"}) is False
    assert h2._send_failures == 1


def test_chain_clone_rocks_checkpoint_fail_closed():
    clone_py = Path("storage/chain_clone.py").read_text(encoding="utf-8")
    assert "Fail-closed: when RocksEngine is available" in clone_py
    assert "engine.checkpoint(str(dst))" in clone_py
    # Must not swallow checkpoint errors before copytree when native Rocks exists.
    assert "except Exception:\n        pass\n    shutil.copytree" not in clone_py


def test_sqlite_decode_fail_closed():
    from storage.database import Database

    db = Database(":memory:")
    db.initialize()
    assert db._loads_json_or_none("{bad", context="test") is None
    assert db._json_decode_failures >= 1
    assert db.get_stats().get("json_decode_failures", 0) >= 1
    db.close()


def test_amount_native_required_raises(monkeypatch):
    import runtime.amount as amount
    import crypto.native as native_mod

    monkeypatch.setenv("REQUIRE_NATIVE_CRYPTO", "1")
    monkeypatch.setattr(native_mod, "native_available", lambda: True)

    def _boom(_s):
        raise RuntimeError("native broken")

    monkeypatch.setattr(native_mod, "amount_to_satoshi", _boom)
    amount._native_fallback_warned = False
    try:
        try:
            amount.to_satoshi("1.5")
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "native amount op" in str(exc)
    finally:
        monkeypatch.delenv("REQUIRE_NATIVE_CRYPTO", raising=False)
        amount._native_fallback_warned = False
