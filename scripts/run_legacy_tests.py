#!/usr/bin/env python3
"""Run legacy script tests with timeout and summary."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY = os.path.join(ROOT, "tests", "legacy")
TIMEOUT = 60


def main() -> int:
    passed = []
    failed = []
    skipped = []

    for name in sorted(os.listdir(LEGACY)):
        if not name.startswith("test_") or not name.endswith(".py"):
            continue
        path = os.path.join(LEGACY, name)
        try:
            proc = subprocess.run(
                [sys.executable, path],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                encoding="utf-8",
                errors="replace",
            )
            if proc.returncode == 0:
                passed.append(name)
            else:
                failed.append((name, proc.returncode, proc.stderr[-500:] or proc.stdout[-500:]))
        except subprocess.TimeoutExpired:
            failed.append((name, -1, f"timeout>{TIMEOUT}s"))

    print(f"Legacy scripts: {len(passed)} passed, {len(failed)} failed")
    for name in passed:
        print(f"  OK  {name}")
    for name, code, tail in failed:
        print(f"  FAIL {name} (exit {code})")
        if tail.strip():
            print("       " + tail.strip().replace("\n", "\n       "))

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
