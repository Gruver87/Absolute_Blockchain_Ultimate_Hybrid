#!/usr/bin/env python3
"""Run full test battery: pytest + smoke + legacy scripts."""
import subprocess
import sys

ROOT = __file__.replace("scripts\\run_all_tests.py", "").replace("scripts/run_all_tests.py", "")


def run(cmd: list) -> int:
    print(f"\n>> {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=ROOT or None)


def main() -> int:
    steps = [
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
        [sys.executable, "tests/smoke/merkle_light.py"],
        [sys.executable, "scripts/check_secrets.py"],
        [sys.executable, "scripts/run_legacy_tests.py"],
    ]
    for cmd in steps:
        code = run(cmd)
        if code != 0:
            return code
    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
