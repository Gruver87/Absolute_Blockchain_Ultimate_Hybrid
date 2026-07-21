#!/usr/bin/env python3
"""Stamp release evidence: bridge_decision_off + optional soak report pointer."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _git_tag() -> str:
    try:
        out = subprocess.check_output(
            ["git", "describe", "--tags", "--always"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _load_evidence(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "run_id": f"evidence-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        "steps": [],
    }


def _append_step(path: Path, name: str, result: str, *, notes: str = "", artifact: str = "", tag: str = "") -> None:
    doc = _load_evidence(path)
    if tag:
        doc["git_tag"] = tag
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    step = {"name": name, "result": result, "recorded_at": datetime.now(timezone.utc).isoformat()}
    if notes:
        step["notes"] = notes
    if artifact:
        step["artifact"] = artifact
    doc.setdefault("steps", []).append(step)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record release evidence stamps")
    parser.add_argument("--git-tag", default="", help="Release tag (default: git describe)")
    parser.add_argument(
        "--soak-report",
        default="logs/soak_report_48h.json",
        help="Soak report to reference (must exist for soak stamp)",
    )
    parser.add_argument("--skip-soak", action="store_true", help="Do not record soak stamp")
    parser.add_argument(
        "--out",
        default=os.environ.get("EVIDENCE_RUN_PATH", str(ROOT / "data" / "evidence_run.json")),
        help="Evidence JSON path",
    )
    args = parser.parse_args()

    tag = args.git_tag or _git_tag()
    out = Path(args.out)

    spec = importlib.util.spec_from_file_location(
        "bridge_off_audit_gate", ROOT / "scripts" / "bridge_off_audit_gate.py"
    )
    if spec is None or spec.loader is None:
        print("FAIL: bridge_off_audit_gate.py missing", file=sys.stderr)
        return 1
    gate_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate_mod)
    if int(gate_mod.main()) != 0:
        print("FAIL: bridge_off_audit_gate", file=sys.stderr)
        return 1

    _append_step(
        out,
        "bridge_decision_off",
        "PASS",
        notes=f"bridge_off_audit_gate OK at {tag or 'local'}",
        artifact=str(ROOT / "data" / "bridge_off_audit_gate.json"),
        tag=tag,
    )
    print("recorded bridge_decision_off=PASS")

    if not args.skip_soak:
        soak_path = ROOT / args.soak_report
        if soak_path.is_file():
            soak = json.loads(soak_path.read_text(encoding="utf-8"))
            passed = bool(soak.get("passed"))
            hrs = int(float(soak.get("hours_requested", 0) or 0))
            _append_step(
                out,
                f"soak_{hrs}h_stamp",
                "PASS" if passed else "FAIL",
                notes=f"referenced {soak_path.name} at {tag or 'local'}",
                artifact=str(soak_path),
                tag=tag,
            )
            print(f"recorded soak_{hrs}h_stamp={'PASS' if passed else 'FAIL'}")
        else:
            print(f"WARN: soak report missing: {soak_path}")

    print("OK: release evidence stamped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
