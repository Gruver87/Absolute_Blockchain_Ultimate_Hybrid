#!/usr/bin/env python3
"""Telegram bot bridge/pools command helpers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram_super_bot import AbsoluteBot


def test_resolve_founder_alias(monkeypatch):
    bot = AbsoluteBot()
    monkeypatch.setattr(bot, "_api_get", lambda path, timeout=10: None)
    assert bot._resolve_address("foundation") == "foundation"
    monkeypatch.setattr(
        bot,
        "_api_get",
        lambda path, timeout=10: {"founder_address": "0xfounder00000000000000000000000001"},
    )
    assert bot._resolve_address("founder") == "0xfounder00000000000000000000000001"


def test_show_bridge_formats_enabled(monkeypatch):
    bot = AbsoluteBot()

    def fake_get(path, timeout=10):
        if path == "/bridge":
            return {
                "enabled": True,
                "mode": "rust",
                "auto_confirm_sec": 0,
                "locks": {"total": 3, "pending": 1},
                "rust_binary": "bridge/abs_bridge_bin",
            }
        return None

    sent = []
    monkeypatch.setattr(bot, "_api_get", fake_get)
    monkeypatch.setattr(bot, "send_message", lambda cid, text, **kw: sent.append(text))
    bot.show_bridge(123)
    assert sent
    assert "rust" in sent[0]
    assert "pending: 1" in sent[0]


def test_show_pools_formats_allocations(monkeypatch):
    bot = AbsoluteBot()

    def fake_get(path, timeout=10):
        if path == "/allocation":
            return {
                "allocations": [
                    {"id": "ecosystem", "name": "Ecosystem", "percent": 20, "live_spendable": 1000, "dao_unlocked": True},
                ]
            }
        return None

    sent = []
    monkeypatch.setattr(bot, "_api_get", fake_get)
    monkeypatch.setattr(bot, "send_message", lambda cid, text, **kw: sent.append(text))
    bot.show_pools(1)
    assert "Ecosystem" in sent[0]
    assert "spendable=1,000" in sent[0]
