#!/usr/bin/env python3
"""Pre-mainnet static audit runner (local gate before external security review)."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.external_audit import DEFAULT_CHECKLIST as EXTERNAL_CHECKLIST

def _load_prod_gate():
    spec = importlib.util.spec_from_file_location("prod_gate", ROOT / "scripts" / "prod_gate.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _file_exists(rel: str) -> bool:
    return (ROOT / rel).is_file()


def run_checks() -> Tuple[List[str], List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    prod_gate = _load_prod_gate()
    for path in prod_gate.PROD_FILES:
        errors.extend(prod_gate.check_file(path))

    try:
        from crypto import native as nc
        require = os.environ.get("ABS_REQUIRE_NATIVE_CRYPTO", "").lower() in ("1", "true", "yes", "on")
        if require and not nc.native_available():
            errors.append("abs_native wheel not available (ABS_REQUIRE_NATIVE_CRYPTO)")
        elif not nc.native_available():
            warnings.append("abs_native wheel not built (dev OK, prod requires wheel)")
    except Exception as exc:
        errors.append(f"native crypto import failed: {exc}")

    required_paths = [
        "validators.manifest.example.json",
        "scripts/verify_p2p_ci.py",
        "scripts/prod_gate.py",
        "scripts/native_bridge_helper.py",
        "scripts/mainnet_readiness.py",
        "scripts/genesis_ceremony.py",
        "runtime/prod_smoke_profile.py",
        "node.prod.mainnet-v1.example.json",
        "scripts/external_audit_tracker.py",
        "runtime/external_audit.py",
        "consensus/cross_shard_coordinator.py",
        "runtime/validator_key_provider.py",
        "docs/PORTING_ROADMAP.md",
    ]
    for rel in required_paths:
        if not _file_exists(rel):
            errors.append(f"missing required artifact: {rel}")

    try:
        from consensus.cross_shard_coordinator import CrossShardCoordinator
        coord = CrossShardCoordinator(2)
        coord.begin("audit", 0, 1)
        if coord.quorum_reached("audit"):
            errors.append("cross_shard coordinator quorum sanity check failed")
    except Exception as exc:
        errors.append(f"cross_shard coordinator import failed: {exc}")

    try:
        from runtime.validator_key_provider import (
            AwsKmsKeyProvider,
            GcpCloudHsmKeyProvider,
            GcpKmsKeyProvider,
            build_validator_key_provider,
        )
        assert build_validator_key_provider() is not None
        assert GcpKmsKeyProvider and GcpCloudHsmKeyProvider and AwsKmsKeyProvider
    except Exception as exc:
        errors.append(f"validator key provider wiring failed: {exc}")

    manifest = ROOT / "validators.manifest.example.json"
    if manifest.is_file():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            validators = data.get("validators") or []
            if not validators:
                warnings.append("validators.manifest.example.json has no validators")
            for row in validators:
                if not isinstance(row, dict):
                    continue
                if not str(row.get("address", "")).startswith("0x"):
                    warnings.append("manifest validator missing explicit 0x address")
                    break
        except json.JSONDecodeError:
            errors.append("validators.manifest.example.json is not valid JSON")

    return errors, warnings, list(EXTERNAL_CHECKLIST)


def write_report(errors: List[str], warnings: List[str], checklist: List[str]) -> Path:
    out = ROOT / "data" / "pre_mainnet_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "external_checklist": checklist,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Pre-mainnet static audit")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout")
    args = parser.parse_args()

    errors, warnings, checklist = run_checks()
    report_path = write_report(errors, warnings, checklist)

    if args.json:
        print(json.dumps({
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "report": str(report_path),
        }, indent=2))
    else:
        print("Pre-mainnet audit")
        print("=================")
        if errors:
            print("FAIL: blocking issues")
            for err in errors:
                print(f"  - {err}")
        else:
            print("OK: automated static checks passed")
        if warnings:
            print("\nWarnings:")
            for warn in warnings:
                print(f"  ! {warn}")
        print("\nExternal review checklist:")
        for item in checklist:
            print(f"  [ ] {item}")
        print(f"\nReport: {report_path}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
