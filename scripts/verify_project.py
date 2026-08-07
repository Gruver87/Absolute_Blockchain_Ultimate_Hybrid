#!/usr/bin/env python3
"""Absolute Blockchain — ONE cross-platform project self-check.

Windows operators usually prefer::

    .\\scripts\\verify_project.ps1 -Mode Industrial

This Python twin covers Linux/macOS / CI-like offline checks without PowerShell::

    python scripts/verify_project.py --mode quick
    python scripts/verify_project.py --mode standard
    python scripts/verify_project.py --mode industrial

Honesty: PASS != public mainnet / firm audit PDF.
Report: data/verify_project.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(name: str, cmd: list[str], steps: list[str]) -> None:
    print(f"\n>>> {name}", flush=True)
    print("    $ " + " ".join(cmd), flush=True)
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        raise SystemExit(f"STEP FAIL: {name} (exit {rc})")
    steps.append(name)
    print(f"OK: {name}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Unified Absolute Blockchain project verify")
    ap.add_argument(
        "--mode",
        choices=("quick", "standard", "industrial"),
        default="quick",
        help="quick=waves+gate; standard=+prod/bridge; industrial=+48h soak evidence",
    )
    ap.add_argument("--min-soak-hours", type=float, default=48.0)
    ap.add_argument("--skip-pytest", action="store_true", help="standard: skip critical pytest")
    args = ap.parse_args()

    started = time.time()
    steps: list[str] = []
    report: dict = {
        "script": "verify_project.py",
        "mode": args.mode,
        "min_soak_hours": args.min_soak_hours,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "steps": steps,
        "ok": False,
        "honesty": [
            "PASS is not public mainnet",
            "external firm audit PDF still required for 'audited'",
            "bridge must stay OFF on live mesh without audited L1 cutover",
            "industrial mode checks packaged tip-v2 soak evidence (operator-local)",
        ],
    }

    print("=" * 72)
    print(f" VERIFY PROJECT  mode={args.mode}")
    print(f" Repo: {ROOT}")
    print(" Honesty: green != launched public mainnet")
    print("=" * 72)

    try:
        env_python = [sys.executable]
        _run(
            "node_version",
            env_python + ["-c", "from runtime.config import Config; print(Config().node_version)"],
            steps,
        )
        _run(
            "ceremony_status",
            env_python + ["scripts/ceremony_status.py", "--json", "data/ceremony_status.json"],
            steps,
        )
        _run(
            "verify_industrial_waves",
            env_python + ["scripts/verify_industrial_waves.py"],
            steps,
        )

        if args.mode in ("standard", "industrial"):
            _run("check_secrets", env_python + ["scripts/check_secrets.py"], steps)
            _run("prod_gate", env_python + ["scripts/prod_gate.py"], steps)
            _run("bridge_off_audit_gate", env_python + ["scripts/bridge_off_audit_gate.py"], steps)
            if not args.skip_pytest:
                _run(
                    "pytest_unit_quick",
                    env_python + ["-m", "pytest", "tests/unit", "-q", "--tb=line", "-x"],
                    steps,
                )

        if args.mode == "industrial":
            _run(
                f"industrial_gate:min_soak={args.min_soak_hours}",
                env_python
                + [
                    "scripts/industrial_gate.py",
                    "--min-soak-hours",
                    str(args.min_soak_hours),
                ],
                steps,
            )
            _run(
                "external_audit_tracker",
                env_python + ["scripts/external_audit_tracker.py", "--list"],
                steps,
            )

        report["ok"] = True
    except SystemExit as exc:
        report["error"] = str(exc)
        print(f"\nFAIL: {exc}", flush=True)
    except Exception as exc:  # noqa: BLE001 — top-level operator report
        report["error"] = str(exc)
        print(f"\nFAIL: {exc}", flush=True)

    report["ended_utc"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_sec"] = round(time.time() - started, 1)
    report["steps"] = steps

    out_dir = ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "verify_project.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=" * 72)
    status = "PASS" if report["ok"] else "FAIL"
    print(f" {status} - mode={args.mode} ({report['elapsed_sec']}s)")
    print("=" * 72)
    print(f"Steps: {', '.join(steps)}")
    print(f"Report: {out_path}")
    print("Honesty:")
    for line in report["honesty"]:
        print(f"  - {line}")

    # Windows tip when operator wants Full/Max (native rebuild / live / P2P)
    if report["ok"]:
        print("\nWindows Full/Max (native rebuild / live / P2P CI):")
        print("  .\\scripts\\verify_project.ps1 -Mode Max")

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
