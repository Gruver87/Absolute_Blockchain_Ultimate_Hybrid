#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preflight checks before starting a long prod-mesh soak (does NOT start soak)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROD_MESH_URLS = (
    "http://127.0.0.1:18180",
    "http://127.0.0.1:18181",
    "http://127.0.0.1:18182",
)


def _git_tag() -> str:
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def run_soak_preflight(*, hours: int = 48, interval_sec: int = 300, require_p2p_tls: bool = False) -> tuple[list[str], list[str], dict]:
    import importlib.util

    vp_path = ROOT / "scripts" / "verify_p2p_ci.py"
    spec = importlib.util.spec_from_file_location("verify_p2p_ci", vp_path)
    vp = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(vp)
    _api = vp._api
    _consistency_harness = vp._consistency_harness
    _fetch_p2p_security = vp._fetch_p2p_security
    _probe_health = vp._probe_health
    verify_p2p_security_mesh = vp.verify_p2p_security_mesh

    errors: list[str] = []
    warnings: list[str] = []
    urls = list(PROD_MESH_URLS)
    nodes: list[dict] = []

    active_path = ROOT / "logs" / "soak_active.json"
    if active_path.is_file():
        try:
            active = json.loads(active_path.read_text(encoding="utf-8"))
            warnings.append(
                "soak_active.json present — another soak may be running "
                f"(started {active.get('started_at', '?')})"
            )
        except (OSError, json.JSONDecodeError):
            warnings.append("soak_active.json present but unreadable")

    for i, url in enumerate(urls, start=1):
        row = {"url": url, "reachable": False}
        if not _probe_health(url, timeout=5):
            errors.append(f"node{i} not reachable at {url}")
            nodes.append(row)
            continue
        row["reachable"] = True
        try:
            st = _api(f"{url}/status", timeout=12)
            row["height"] = int(st.get("height", 0) or 0)
            row["peers"] = int(st.get("peers", st.get("peer_count", 0)) or 0)
            row["deployment_mode"] = st.get("deployment_mode")
            row["p2p_sync_status"] = st.get("p2p_sync_status")
            if str(st.get("deployment_mode", "")).lower() != "prod":
                warnings.append(f"node{i} deployment_mode={st.get('deployment_mode')!r}")
        except OSError as exc:
            errors.append(f"node{i} /status: {exc}")
        try:
            sec, source = _fetch_p2p_security(url)
            row["p2p_security_source"] = source
            row["rate_limit_per_sec"] = int((sec or {}).get("rate_limit_per_sec", 0) or 0)
            tls = (sec or {}).get("tls") or {}
            row["p2p_tls_enabled"] = bool(tls.get("enabled"))
            row["p2p_tls_ready"] = bool(tls.get("ready"))
            if tls.get("enabled") and not tls.get("ready"):
                msg = f"node{i} P2P TLS enabled but not ready"
                if require_p2p_tls:
                    errors.append(msg)
                else:
                    warnings.append(msg)
            if require_p2p_tls and not tls.get("enabled"):
                errors.append(f"node{i} P2P TLS not enabled (use docker_prod_3node.ps1 -P2pTls)")
        except OSError as exc:
            warnings.append(f"node{i} p2p security: {exc}")
        nodes.append(row)

    reachable = [u for u in urls if _probe_health(u, timeout=3)]
    if len(reachable) >= 2:
        heights = [n.get("height", 0) for n in nodes if n.get("reachable")]
        if heights and max(heights) - min(heights) > 1:
            errors.append(f"height spread across mesh: {heights}")
        heads = []
        for url in reachable:
            try:
                heads.append(str(_api(f"{url}/status", timeout=8).get("head_hash") or "").lower())
            except OSError:
                pass
        if heads and len(set(h for h in heads if h)) > 1:
            errors.append("head hash mismatch across reachable nodes")

    if len(reachable) == len(urls):
        sec_rc = verify_p2p_security_mesh(urls)
        if sec_rc != 0:
            errors.append("verify_p2p_security_mesh failed (see stdout above)")

    if reachable:
        try:
            harness = _consistency_harness(reachable[0])
            if not harness.get("harness_healthy"):
                failed = harness.get("failed_checks") or []
                errors.append(f"harness unhealthy: {failed}")
        except OSError as exc:
            errors.append(f"harness: {exc}")
        try:
            topo = _api(f"{reachable[0]}/p2p/topology", timeout=12)
            if int(topo.get("peer_count", 0) or 0) < 2:
                warnings.append(
                    f"leader peer_count={topo.get('peer_count')} (prefer >=2 before 48h soak)"
                )
        except OSError as exc:
            warnings.append(f"topology: {exc}")

    tag = _git_tag()
    start_cmd = (
        f".\\scripts\\restart_soak_prod_mesh.ps1 -Hours {hours} "
        f"-IntervalSec {interval_sec} -ReportFile logs/soak_report_48h.json"
    )
    meta = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ready": not errors,
        "hours_planned": hours,
        "interval_sec": interval_sec,
        "git_tag": tag,
        "nodes": nodes,
        "start_command": start_cmd,
        "after_complete": (
            f"python scripts/industrial_gate.py --min-soak-hours {hours}"
        ),
        "note": "Run preflight again immediately before starting soak.",
        "require_p2p_tls": require_p2p_tls,
    }
    return errors, warnings, meta


def write_report(errors: list[str], warnings: list[str], meta: dict) -> Path:
    out = ROOT / "logs" / "soak_preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        **meta,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Prod mesh soak preflight (no soak start)")
    parser.add_argument("--hours", type=int, default=48, help="Planned soak duration")
    parser.add_argument("--interval-sec", type=int, default=300, help="Planned poll interval")
    parser.add_argument(
        "--require-p2p-tls",
        action="store_true",
        help="Fail if prod mesh P2P wire TLS is not enabled and ready on all nodes",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    errors, warnings, meta = run_soak_preflight(
        hours=args.hours,
        interval_sec=args.interval_sec,
        require_p2p_tls=args.require_p2p_tls,
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
                    **meta,
                },
                indent=2,
            )
        )
    else:
        print("=" * 60)
        print("SOAK PREFLIGHT (prod mesh :18180-:18182)")
        print("=" * 60)
        if errors:
            print("RESULT: NOT READY")
            for err in errors:
                print(f"  - {err}")
        else:
            print("RESULT: READY for soak")
        for warn in warnings:
            print(f"  WARN: {warn}")
        print(f"Report: {report_path}")
        if not errors:
            print("")
            print("When you are ready to start (not now unless intended):")
            print(f"  {meta['start_command']}")
            print("")
            print("After soak completes:")
            print(f"  {meta['after_complete']}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
