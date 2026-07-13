#!/usr/bin/env python3
"""Monolith readiness gate — one report for industrial + mainnet + launch checklist."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_monolith_gate(
    *,
    strict_audit: bool = False,
    bridge_cutover: bool = False,
    live_prod_mesh: bool = False,
    ceremony_dir: str = "",
    p2p_ci: bool = False,
    soak_preflight: bool = False,
    probe_l1: bool = False,
    bridge_live: bool = False,
    skip_launch_checklist: bool = False,
) -> Tuple[List[str], List[str], dict]:
    errors: List[str] = []
    warnings: List[str] = []
    sections: dict = {}

    import importlib.util

    ig_spec = importlib.util.spec_from_file_location(
        "industrial_gate", ROOT / "scripts" / "industrial_gate.py"
    )
    industrial = importlib.util.module_from_spec(ig_spec)
    assert ig_spec.loader is not None
    ig_spec.loader.exec_module(industrial)

    ig_rc = industrial.run_industrial_gate(
        ceremony_dir=ceremony_dir,
        strict_audit=strict_audit,
        bridge_cutover=bridge_cutover,
        live_prod_mesh=live_prod_mesh,
        probe_l1=probe_l1,
        bridge_live=bridge_live,
    )
    sections["industrial_gate"] = {"rc": ig_rc}
    if ig_rc != 0:
        errors.append("industrial_gate failed")
    ig_path = ROOT / "data" / "industrial_gate.json"
    if ig_path.is_file():
        try:
            ig_report = json.loads(ig_path.read_text(encoding="utf-8"))
            warnings.extend(ig_report.get("warnings") or [])
            sections["industrial_gate"]["warnings"] = ig_report.get("warnings") or []
        except (OSError, json.JSONDecodeError):
            pass

    if not skip_launch_checklist:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "mainnet_launch_checklist",
            ROOT / "scripts" / "mainnet_launch_checklist.py",
        )
        launch = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(launch)
        lc_errors, lc_warnings = launch.run_launch_checklist(
            bridge_cutover=bridge_cutover,
            ceremony_dir=ceremony_dir,
            skip_industrial=True,
            skip_duplicate_gates=True,
        )
        errors.extend([f"launch:{e}" for e in lc_errors])
        warnings.extend(lc_warnings)
        sections["launch_checklist"] = {"errors": lc_errors, "warnings": lc_warnings}

    if p2p_ci:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_p2p_ci.py"), "--mode", "ci"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        sections["p2p_ci"] = {"rc": proc.returncode}
        if proc.returncode != 0:
            detail = (proc.stdout or proc.stderr or "").strip()
            errors.append(f"p2p_ci failed: {detail or proc.returncode}")

    if soak_preflight:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "soak_preflight", ROOT / "scripts" / "soak_preflight.py"
        )
        soak_mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(soak_mod)
        sf_errors, sf_warnings, sf_meta = soak_mod.run_soak_preflight(hours=48)
        soak_mod.write_report(sf_errors, sf_warnings, sf_meta)
        sections["soak_preflight"] = {
            "ready": sf_meta.get("ready"),
            "errors": sf_errors,
            "warnings": sf_warnings,
        }
        errors.extend([f"soak_preflight:{e}" for e in sf_errors])
        warnings.extend(sf_warnings)

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strict_audit": strict_audit,
        "bridge_cutover": bridge_cutover,
        "live_prod_mesh": live_prod_mesh,
        "p2p_ci": p2p_ci,
        "soak_preflight": soak_preflight,
        "probe_l1": probe_l1,
        "bridge_live": bridge_live,
        "sections": sections,
    }
    return errors, warnings, meta


def write_report(errors: List[str], warnings: List[str], meta: dict) -> Path:
    out = ROOT / "data" / "monolith_gate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        **meta,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Monolith readiness gate (unified static report)")
    parser.add_argument(
        "--strict-audit",
        action="store_true",
        help="Fail on incomplete external audit checklist",
    )
    parser.add_argument(
        "--bridge-cutover",
        action="store_true",
        help="Include bridge L1 cutover static gate",
    )
    parser.add_argument(
        "--live-prod-mesh",
        action="store_true",
        help="Include live prod mesh checks (:18180-:18182)",
    )
    parser.add_argument("--ceremony-dir", default="", help="Ceremony directory for pin checks")
    parser.add_argument(
        "--p2p-ci",
        action="store_true",
        help="Run verify_p2p_ci --mode ci (isolated 2-node spawn)",
    )
    parser.add_argument(
        "--skip-launch-checklist",
        action="store_true",
        help="Skip mainnet_launch_checklist layer (faster dev loop)",
    )
    parser.add_argument(
        "--soak-preflight",
        action="store_true",
        help="Check prod mesh readiness for 48h soak (does not start soak)",
    )
    parser.add_argument(
        "--probe-l1",
        action="store_true",
        help="With --bridge-cutover, probe L1 RPC and contract bytecode",
    )
    parser.add_argument(
        "--bridge-live",
        action="store_true",
        help="With --bridge-cutover, live bridge node checks",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings, meta = run_monolith_gate(
        strict_audit=args.strict_audit,
        bridge_cutover=args.bridge_cutover,
        live_prod_mesh=args.live_prod_mesh,
        ceremony_dir=args.ceremony_dir,
        p2p_ci=args.p2p_ci,
        soak_preflight=args.soak_preflight,
        probe_l1=args.probe_l1,
        bridge_live=args.bridge_live,
        skip_launch_checklist=args.skip_launch_checklist,
    )
    report_path = write_report(errors, warnings, meta)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not errors,
                    "errors": errors,
                    "warnings": warnings,
                    "report": str(report_path),
                },
                indent=2,
            )
        )
    else:
        print("=" * 60)
        print("MONOLITH READINESS GATE")
        print("=" * 60)
        if errors:
            print("RESULT: FAIL")
            for err in errors:
                print(f"  - {err}")
        else:
            print("RESULT: OK — monolith static gates passed")
        if warnings:
            print("\nWarnings:")
            for warn in warnings:
                print(f"  ! {warn}")
        print(f"\nReport: {report_path}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
