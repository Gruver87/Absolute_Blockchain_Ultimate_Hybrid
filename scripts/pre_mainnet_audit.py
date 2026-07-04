#!/usr/bin/env python3
"""Pre-mainnet static audit runner (local gate before external security review)."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_prod_gate():
    spec = importlib.util.spec_from_file_location("prod_gate", ROOT / "scripts" / "prod_gate.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def run_checks() -> list[str]:
    errors: list[str] = []
    prod_gate = _load_prod_gate()
    for path in prod_gate.PROD_FILES:
        errors.extend(prod_gate.check_file(path))

    try:
        from crypto import native as nc
        require = os.environ.get("ABS_REQUIRE_NATIVE_CRYPTO", "").lower() in ("1", "true", "yes", "on")
        if require and not nc.native_available():
            errors.append("abs_native wheel not available (ABS_REQUIRE_NATIVE_CRYPTO)")
    except Exception as exc:
        errors.append(f"native crypto import failed: {exc}")

    manifest = ROOT / "validators.manifest.example.json"
    if not manifest.is_file():
        errors.append("validators.manifest.example.json missing")

    checklist = [
        "External penetration test scheduled",
        "Bridge L1 RPC keys rotated from dev placeholders",
        "Validator keys not stored in node.json / git",
        "CORS and RPC API keys reviewed for production origins",
        "Incident response runbook documented",
    ]
    return errors, checklist


def main() -> int:
    errors, checklist = run_checks()
    print("Pre-mainnet audit")
    print("=================")
    if errors:
        print("FAIL: blocking issues")
        for err in errors:
            print(f"  - {err}")
    else:
        print("OK: automated static checks passed")
    print("\nExternal review checklist:")
    for item in checklist:
        print(f"  [ ] {item}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
