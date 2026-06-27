#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сканер секретов перед коммитом/push.
Не допускает в git: API keys, bot tokens, private keys, пароли.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {
    ".git", "__pycache__", ".pytest_cache", "venv", ".venv",
    "data", "_archive", "absolute-blockchain-ultimate", "nft_images",
    ".hypothesis", "backup_",
}

SKIP_FILES = {
    ".env", "wallet.json", "data/wallet.json",
}

SCAN_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yml", ".yaml", ".ps1", ".bat", ".sh", ".env", ".example",
}

# Плейсхолдеры в .example — разрешены
PLACEHOLDER_MARKERS = (
    "your_", "YOUR_", "placeholder", "example", "changeme", "xxx", "TODO",
)

PATTERNS = [
    (r"(?i)(openweather_api_key|weatherapi_key)\s*[=:]\s*['\"]([a-f0-9]{20,})['\"]", "Weather API key"),
    (r"(?i)telegram_bot_token\s*[=:]\s*['\"]?(\d{8,}:[A-Za-z0-9_-]{30,})['\"]?", "Telegram bot token"),
    (r"(?i)jwt_secret\s*[=:]\s*['\"]([^'\"]{16,})['\"]", "JWT secret"),
    (r"(?i)['\"]private_key['\"]\s*:\s*['\"]([0-9a-f]{64,})['\"]", "Private key (hex)"),
    (r"(?i)(password|passwd)\s*[=:]\s*['\"]([^'\"]{6,})['\"]", "Password"),
    (r"ngrok.*?[=:]\s*['\"]([A-Za-z0-9_]{20,})['\"]", "Ngrok token"),
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style API key"),
    (r"(?i)private\s*key\s*:\s*([0-9a-f]{64,})", "Private key in text file"),
    (r"(?i)github_token\s*[=:]\s*['\"]?(ghp_[A-Za-z0-9]{20,})", "GitHub personal access token"),
    (r"gho_[A-Za-z0-9]{20,}", "GitHub OAuth token"),
]


def _is_placeholder(value: str) -> bool:
    low = value.lower()
    return any(m in low for m in PLACEHOLDER_MARKERS)


def scan_file(path: str) -> list:
    findings = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError:
        return findings

    rel = os.path.relpath(path, ROOT)
    if rel.replace("\\", "/") in SKIP_FILES:
        return findings

    for pattern, label in PATTERNS:
        for m in re.finditer(pattern, content):
            captured = m.group(m.lastindex or 0)
            if _is_placeholder(captured):
                continue
            line = content[: m.start()].count("\n") + 1
            findings.append((rel, line, label, captured[:12] + "…"))
    return findings


def main() -> int:
    all_findings = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS and not d.startswith("backup_")
        ]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in SCAN_EXTENSIONS and name not in (".env", ".env.example"):
                continue
            path = os.path.join(dirpath, name)
            if name == ".env" or name.startswith(".env.") and name != ".env.example":
                continue
            all_findings.extend(scan_file(path))

    if not all_findings:
        print("OK: no secrets detected in scanned files")
        return 0

    print("FAIL: potential secrets found:")
    for rel, line, label, preview in all_findings:
        print(f"  {rel}:{line}  [{label}]  {preview}")
    print("\nRotate exposed keys and move secrets to .env (never commit).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
