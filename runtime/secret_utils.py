#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка плейсхолдеров в секретах (.env)."""

_PLACEHOLDER_MARKERS = (
    "your_", "your-", "changeme", "placeholder", "example", "xxx", "todo",
    "token_here", "api_key_here", "secret_here", "insert_", "replace_",
)


def is_placeholder_secret(value: str) -> bool:
    """True если значение из .env.example, а не реальный секрет."""
    if not value or not value.strip():
        return True
    low = value.strip().lower()
    if low in ("", "none", "null", "false", "0"):
        return True
    return any(m in low for m in _PLACEHOLDER_MARKERS)
