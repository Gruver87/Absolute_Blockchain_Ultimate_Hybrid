#!/usr/bin/env python3
"""Verify incident response runbook is present and complete."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SECTIONS = (
    "Severity",
    "Disaster recovery",
    "Secret compromise",
    "P2P partition",
    "State root mismatch",
)


def check_runbook(path: Path | None = None) -> tuple[bool, str]:
    doc = path or (ROOT / "docs" / "INCIDENT_RESPONSE.md")
    if not doc.is_file():
        return False, f"missing {doc.relative_to(ROOT)}"
    text = doc.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SECTIONS if s.lower() not in text.lower()]
    if missing:
        return False, f"missing sections: {', '.join(missing)}"
    if len(text.strip()) < 800:
        return False, "runbook too short"
    return True, str(doc.relative_to(ROOT))


def main() -> int:
    ok, note = check_runbook()
    if ok:
        print(f"OK: incident runbook ({note})")
        return 0
    print(f"FAIL: incident runbook — {note}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
