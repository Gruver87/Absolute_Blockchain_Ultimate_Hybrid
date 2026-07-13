#!/usr/bin/env python3
"""Static + optional live gate for public testnet (chain 77777) deployment."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_REQUIRED_FILES = (
    "docker-compose.testnet.yml",
    ".env.testnet.example",
    "docker/node.testnet.seed.json",
    "deploy/nginx/testnet.example.conf",
    "deploy/nginx/install_testnet_nginx.sh",
    "scripts/docker_testnet_seed.ps1",
    "scripts/vps_testnet_preflight.py",
    "scripts/vps_testnet_bootstrap.sh",
    "scripts/testnet_uptime_probe.py",
    "scripts/verify_testnet_mesh.py",
    "scripts/docker_testnet_mesh.ps1",
    "scripts/probe_testnet_mesh.ps1",
    "scripts/testnet_readiness.ps1",
    "docs/PUBLIC_TESTNET.md",
)

_REQUIRED_MESH3_FILES = (
    "docker-compose.testnet.mesh3.yml",
    "docker/node.testnet.validator3.json",
    "scripts/docker_testnet_mesh3.ps1",
    "scripts/testnet_health_watch.ps1",
)


def _probe_http(base_url: str, timeout: float = 8.0) -> Tuple[List[str], Dict[str, Any]]:
    errors: List[str] = []
    meta: Dict[str, Any] = {"base_url": base_url.rstrip("/")}
    base = base_url.rstrip("/")

    def _get(path: str) -> Dict[str, Any]:
        req = urllib.request.Request(f"{base}{path}", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            loc = ""
            if exc.headers:
                loc = str(exc.headers.get("Location") or "")
            if exc.code in (301, 302, 303, 307, 308):
                hint = (
                    f"{path}: HTTP {exc.code} redirect to {loc!r} — "
                    "port is not an ABS node (Windows Nahimic often binds :9080). "
                    "Use TESTNET_HTTP_PORT=19080 in .env.testnet and re-run docker_testnet_seed.ps1"
                )
                raise urllib.error.URLError(hint) from exc
            raise

    try:
        ready = _get("/health/ready")
        meta["ready"] = ready
        if str(ready.get("status", "")).lower() != "ready":
            errors.append(f"health/ready status={ready.get('status')}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"health/ready: {exc}")
        return errors, meta

    try:
        status = _get("/status")
        meta["status"] = status
        chain_id = int(status.get("chain_id", 0) or 0)
        if chain_id != 77777:
            errors.append(f"expected chain_id=77777 got {chain_id}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"status: {exc}")

    try:
        harness = _get("/chain/consistency/harness?quick=1&peer_timeout=5")
        meta["harness"] = {
            "harness_healthy": harness.get("harness_healthy"),
            "tip_state_aligned": harness.get("tip_state_aligned"),
        }
        if not harness.get("harness_healthy"):
            errors.append("harness not healthy")
        if not harness.get("tip_state_aligned"):
            errors.append("tip_state not aligned")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"harness: {exc}")

    return errors, meta


def run_public_testnet_gate(
    *,
    live: bool = False,
    base_url: str = "http://127.0.0.1:19080",
    require_soak_hours: float = 0,
    soak_report: str = "logs/soak_report.json",
    mesh: bool = False,
    mesh3: bool = False,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    errors: List[str] = []
    warnings: List[str] = []
    meta: Dict[str, Any] = {"live": live, "chain_id": 77777}

    for rel in _REQUIRED_FILES:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing:{rel}")

    if mesh3:
        for rel in _REQUIRED_MESH3_FILES:
            path = ROOT / rel
            if not path.is_file():
                errors.append(f"missing:{rel}")

    explorer = ROOT / "web" / "explorer"
    if not explorer.is_dir():
        warnings.append("web/explorer missing — static explorer not bundled")

    env_example = ROOT / ".env.testnet.example"
    if env_example.is_file():
        text = env_example.read_text(encoding="utf-8")
        for key in ("JWT_SECRET", "RPC_API_KEYS", "CORS_ORIGINS"):
            if key not in text:
                warnings.append(f".env.testnet.example missing {key}")

    if require_soak_hours > 0:
        soak_path = ROOT / soak_report
        if not soak_path.is_file():
            errors.append(f"soak_report missing for public testnet ({soak_path})")
        else:
            try:
                soak = json.loads(soak_path.read_text(encoding="utf-8"))
                meta["soak"] = soak
                hrs = float(soak.get("hours_requested", 0) or 0)
                if hrs < require_soak_hours:
                    errors.append(f"soak hours_requested={hrs} < {require_soak_hours}")
                if not soak.get("passed"):
                    errors.append("soak_report passed=false")
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                errors.append(f"soak_report unreadable: {exc}")

    warnings.extend(
        [
            "public_dns_tls: not automated — configure nginx + Let's Encrypt before DNS",
            "vps_hosting: operator must provision cloud VM and open ports 443/19080/19085",
        ]
    )

    if live:
        live_errors, live_meta = _probe_http(base_url)
        meta.update(live_meta)
        errors.extend([f"live:{e}" for e in live_errors])

    if mesh or mesh3:
        sys.path.insert(0, str(ROOT / "scripts"))
        import verify_testnet_mesh

        validator_urls = (
            list(verify_testnet_mesh.DEFAULT_MESH3)
            if mesh3
            else ["http://127.0.0.1:19081"]
        )
        mesh_errors, mesh_warnings, mesh_meta = verify_testnet_mesh.verify_testnet_mesh(
            seed_url=base_url,
            validator_urls=validator_urls,
            wait_sec=0,
        )
        meta["mesh_verify"] = mesh_meta
        errors.extend([f"mesh:{e}" for e in mesh_errors])
        warnings.extend(mesh_warnings)

    meta["ok"] = not errors
    return errors, warnings, meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Public testnet deployment gate (chain 77777)")
    parser.add_argument("--live", action="store_true", help="Probe running testnet seed HTTP")
    parser.add_argument("--base-url", default="http://127.0.0.1:19080")
    parser.add_argument(
        "--require-soak-hours",
        type=float,
        default=0,
        help="Require prod mesh soak_report hours (0=skip)",
    )
    parser.add_argument("--soak-report", default="logs/soak_report.json")
    parser.add_argument(
        "--mesh",
        action="store_true",
        help="Also verify 2-node mesh on :19080/:19081",
    )
    parser.add_argument(
        "--mesh3",
        action="store_true",
        help="Also verify 3-node mesh on :19080/:19081/:19082",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings, meta = run_public_testnet_gate(
        live=args.live,
        base_url=args.base_url,
        require_soak_hours=args.require_soak_hours,
        soak_report=args.soak_report,
        mesh=args.mesh,
        mesh3=args.mesh3,
    )

    out = ROOT / "data" / "public_testnet_gate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"errors": errors, "warnings": warnings, **meta}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
    elif errors:
        print("FAIL: public testnet gate")
        for err in errors:
            print(f"  - {err}")
    else:
        print("OK: public testnet gate")
    for warn in warnings:
        print(f"  WARN: {warn}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
