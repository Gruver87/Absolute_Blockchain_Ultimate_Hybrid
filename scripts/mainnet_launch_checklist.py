#!/usr/bin/env python3
"""Pre-launch checklist — code gates + audit status (single command)."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _run_script(rel: str, attr: str = "main") -> tuple[int, str]:
    path = ROOT / "scripts" / rel
    spec = importlib.util.spec_from_file_location(rel.replace("/", "_"), path)
    if spec is None or spec.loader is None:
        return 127, f"missing {rel}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if rel == "backup_db_drill.py" and hasattr(mod, "run_backup_drill"):
        return int(mod.run_backup_drill()), rel
    fn = getattr(mod, attr)
    argv = sys.argv
    try:
        sys.argv = [rel]
        return int(fn()), rel
    finally:
        sys.argv = argv


def run_launch_checklist(*, strict_mainnet: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    steps = [
        ("prod_gate.py", "Production static gate"),
        ("runbook_check.py", "Incident runbook"),
        ("backup_db_drill.py", "DR backup drill"),
        ("evm_opcode_parity_gate.py", "EVM opcode parity"),
    ]
    for script, label in steps:
        rc, name = _run_script(script)
        if rc != 0:
            errors.append(f"{label} failed ({name} exit {rc})")

    from runtime.genesis_ceremony import build_from_paths

    artifact, ceremony_errors = build_from_paths(
        str(ROOT / "node.prod.mainnet-v1.example.json"),
        str(ROOT / "validators.manifest.example.json"),
        strict_addresses=strict_mainnet,
    )
    if ceremony_errors:
        errors.extend([f"genesis_ceremony:{e}" for e in ceremony_errors])
    elif not artifact.get("mainnet_addresses_ready", True):
        warnings.append(
            "genesis: replace placeholder validator addresses before public mainnet "
            f"(count={artifact.get('placeholder_validator_count', 0)})"
        )

    rc, _ = _run_script("industrial_gate.py")
    if rc != 0:
        errors.append("industrial_gate failed")

    from runtime.external_audit import evaluate

    audit_warnings, _, summary = evaluate()
    pending = int(summary.get("pending", 0) or 0)
    if pending:
        warnings.append(f"external_audit: {pending}/8 checklist items pending")
        for w in audit_warnings:
            if "Third-party" in w:
                warnings.append(
                    "blocker: third-party L1/EVM audit — mark done after vendor report: "
                    "python scripts/external_audit_tracker.py --set "
                    "\"Third-party smart-contract / L1 security audit completed\" --note \"vendor+date\""
                )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Mainnet launch checklist (code gates)")
    parser.add_argument(
        "--strict-mainnet",
        action="store_true",
        help="Fail if validator manifest still has placeholder 0x000… addresses",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings = run_launch_checklist(strict_mainnet=args.strict_mainnet)
    payload = {"ok": not errors, "errors": errors, "warnings": warnings}

    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("MAINNET LAUNCH CHECKLIST (code + ops gates)")
        print("=" * 60)
        if errors:
            print("ERRORS:")
            for err in errors:
                print(f"  - {err}")
        if warnings:
            print("WARNINGS:")
            for warn in warnings:
                print(f"  - {warn}")
        if not errors and not warnings:
            print("OK: all automated launch checks passed")
        elif not errors:
            print("OK: code gates passed (see warnings for org blockers)")
        print("=" * 60)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
