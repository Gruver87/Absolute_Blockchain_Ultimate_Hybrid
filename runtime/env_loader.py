#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Загрузка .env и переменных окружения (12-factor)."""

import os
from typing import Optional


def load_dotenv_file(path: str = ".env") -> bool:
    """Загружает .env без обязательной зависимости python-dotenv."""
    try:
        from dotenv import load_dotenv
        return load_dotenv(path)
    except ImportError:
        pass
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    return True


def env_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_list(key: str, default: Optional[list] = None) -> list:
    raw = os.getenv(key, "")
    if not raw.strip():
        return list(default or [])
    return [x.strip() for x in raw.split(",") if x.strip()]
