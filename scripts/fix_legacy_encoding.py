#!/usr/bin/env python3
"""Normalize legacy test scripts to UTF-8 and ensure exit codes."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY = os.path.join(ROOT, "tests", "legacy")

PATH_LINE = (
    "import os, sys\n"
    "sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))\n"
)


def normalize(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        text = content.decode("utf-8", errors="replace")
    text = text.replace("\ufeff", "")
    text = re.sub(r"^(\?+)(#|import|from|#!/)", r"\2", text, flags=re.MULTILINE)
    text = text.replace("\x97", "-").replace("\x96", "-")
    return text


def ensure_header(text: str) -> str:
    if "coding:" in text[:300]:
        return text
    lines = text.splitlines()
    insert_at = 1 if lines and lines[0].startswith("#!") else 0
    lines.insert(insert_at, "# -*- coding: utf-8 -*-")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def ensure_path(text: str) -> str:
    if "sys.path.insert" in text:
        return text
    lines = text.splitlines()
    insert_at = 0
    for i, line in enumerate(lines[:8]):
        if line.startswith("#!") or "coding:" in line:
            insert_at = i + 1
    lines.insert(insert_at, PATH_LINE.rstrip())
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def ensure_exit(text: str) -> str:
    if "sys.exit" in text or "raise SystemExit" in text:
        return text
    if "passed" not in text or "total" not in text:
        return text
    return text.rstrip() + (
        "\nimport sys\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(0 if passed == total else 1)\n"
    )


def main() -> int:
    count = 0
    for name in sorted(os.listdir(LEGACY)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(LEGACY, name)
        raw = open(path, "rb").read()
        text = normalize(raw)
        text = ensure_header(text)
        text = ensure_path(text)
        text = ensure_exit(text)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        count += 1
    print(f"OK: normalized {count} legacy scripts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
