#!/usr/bin/env python3
"""Mainnet readiness gate — prod stack + pre-mainnet audit in one report."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_module(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def run_gate(live: bool = False, base_url: str = "http://127.0.0.1:8080") -> Tuple[List[str], List[str], dict]:
    errors: List[str] = []
    warnings: List[str] = []
    sections: dict = {}

    pre = _load_module("pre_mainnet_audit", "scripts/pre_mainnet_audit.py")
    pre_errors, pre_warnings, checklist = pre.run_checks()
    errors.extend(pre_errors)
    warnings.extend(pre_warnings)
    sections["pre_mainnet"] = {"errors": pre_errors, "warnings": pre_warnings}

    prod = _load_module("verify_prod_stack", "scripts/verify_prod_stack.py")
    prod_errors = []
    prod_errors.extend(prod.check_prod_gate())
    prod_errors.extend(prod.check_config_validate())
    prod_errors.extend(prod.check_docker_prod_compose())
    if live:
        prod_errors.extend(prod.check_live_smoke(base_url.rstrip("/")))
    errors.extend(prod_errors)
    sections["prod_stack"] = {"errors": prod_errors, "live": live}

    return errors, warnings, {
        "external_checklist": checklist,
        "sections": sections,
    }


def write_report(errors: List[str], warnings: List[str], meta: dict) -> Path:
    out = ROOT / "data" / "mainnet_readiness.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        **meta,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Mainnet readiness gate")
    parser.add_argument("--live", action="store_true", help="Include prod_smoke against running node")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    errors, warnings, meta = run_gate(live=args.live, base_url=args.base_url)
    report_path = write_report(errors, warnings, meta)

    if args.json:
        print(json.dumps({
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "report": str(report_path),
        }, indent=2))
    else:
        print("=" * 60)
        print("MAINNET READINESS GATE")
        print("=" * 60)
        if errors:
            print("RESULT: FAIL")
            for err in errors:
                print(f"  - {err}")
        else:
            print("RESULT: OK — ready for external audit + mainnet cutover")
        if warnings:
            print("\nWarnings:")
            for warn in warnings:
                print(f"  ! {warn}")
        print("\nExternal checklist:")
        for item in meta.get("external_checklist", []):
            print(f"  [ ] {item}")
        print(f"\nReport: {report_path}")
        print("=" * 60)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
