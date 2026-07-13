#!/usr/bin/env python3
"""Static + optional live preflight for prod mesh P2P TLS."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def run_p2p_tls_preflight(*, live: bool = False, wait_sec: int = 0) -> tuple[list[str], list[str], dict]:
    import verify_p2p_tls_mesh

    if live:
        return verify_p2p_tls_mesh.verify_p2p_tls_mesh(wait_sec=wait_sec, require_tls=True)

    errors, warnings, meta = verify_p2p_tls_mesh.check_static_tls_material()
    meta["live"] = False
    meta["ready"] = not errors
    meta["deploy_steps"] = [
        "python scripts/gen_p2p_mesh_tls.py",
        ".\\scripts\\docker_prod_3node.ps1 -P2pTls",
        "python scripts/verify_p2p_tls_mesh.py --wait 120",
        ".\\scripts\\p2p_tls_evidence_suite.ps1",
    ]
    return errors, warnings, meta


def write_report(errors: list[str], warnings: list[str], meta: dict) -> Path:
    out = ROOT / "logs" / "p2p_tls_preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": not errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
        "warnings": warnings,
        **meta,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="P2P TLS mesh preflight")
    parser.add_argument("--live", action="store_true", help="Probe running prod mesh nodes")
    parser.add_argument("--wait", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings, meta = run_p2p_tls_preflight(live=args.live, wait_sec=args.wait)
    report = write_report(errors, warnings, meta)

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "report": str(report), **meta}, indent=2))
    else:
        label = "live" if args.live else "static"
        print(f"P2P TLS PREFLIGHT ({label})")
        if errors:
            print("RESULT: FAIL")
            for err in errors:
                print(f"  - {err}")
        else:
            print("RESULT: OK")
        for warn in warnings:
            print(f"  WARN: {warn}")
        print(f"Report: {report}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
