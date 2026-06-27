#!/usr/bin/env python3
"""Telegram bot product/status text stays aligned with the hardened node profile."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from telegram_super_bot import AbsoluteBot


class _Bot(AbsoluteBot):
    def __init__(self, api_payload):
        super().__init__()
        self.api_payload = api_payload
        self.messages = []

    def _api_get(self, path: str, timeout: int = 10):
        return self.api_payload.get(path)

    def send_message(self, chat_id, text, parse_mode=None):
        self.messages.append((chat_id, text, parse_mode))
        return {"ok": True}


def test_about_text_uses_hardened_profile_wording():
    text = AbsoluteBot().get_about_text()

    assert "educational" not in text.lower()
    assert "production-hardened" in text


def test_bridge_status_defaults_to_unknown_not_simulator():
    bot = _Bot({
        "/bridge": {
            "enabled": True,
            "locks": {"total": 0, "pending": 0},
            "auto_confirm_sec": 0,
        }
    })

    bot.show_bridge(123)

    assert "Mode: unknown" in bot.messages[-1][1]
    assert "simulator" not in bot.messages[-1][1].lower()


def test_bridge_status_marks_explicit_dev_simulator():
    bot = _Bot({
        "/bridge": {
            "enabled": True,
            "mode": "simulator",
            "locks": {"total": 1, "pending": 1},
            "auto_confirm_sec": 0,
        }
    })

    bot.show_bridge(123)

    assert "Mode: simulator" in bot.messages[-1][1]
    assert "explicit dev/test simulator mode" in bot.messages[-1][1]
