#!/usr/bin/env python3
"""VPS public testnet preflight (chain 77777) — static + optional live seed probe."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_NGINX_MARKERS = (
    "ssl",
    "limit_req",
    "proxy_pass",
    "abs_testnet_http",
    "abs_testnet_rpc",
)


def run_vps_testnet_preflight(
    *,
    live: bool = False,
    base_url: str = "http://127.0.0.1:19080",
    mesh3: bool = False,
    domain: str = "",
) -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    meta: dict = {"chain_id": 77777, "live": live}

    sys.path.insert(0, str(ROOT / "scripts"))
    from public_testnet_gate import run_public_testnet_gate

    gate_errors, gate_warnings, gate_meta = run_public_testnet_gate(
        live=live,
        base_url=base_url,
        mesh3=mesh3,
    )
    errors.extend(gate_errors)
    warnings.extend(gate_warnings)
    meta["public_gate"] = gate_meta

    nginx_path = ROOT / "deploy" / "nginx" / "testnet.example.conf"
    if nginx_path.is_file():
        text = nginx_path.read_text(encoding="utf-8").lower()
        missing = [m for m in _NGINX_MARKERS if m not in text]
        if missing:
            warnings.append(f"nginx template missing markers: {', '.join(missing)}")
        meta["nginx_template"] = str(nginx_path)
    else:
        errors.append("missing:deploy/nginx/testnet.example.conf")

    env_path = ROOT / ".env.testnet"
    env_example = ROOT / ".env.testnet.example"
    if env_path.is_file():
        meta["env_file"] = str(env_path)
        text = env_path.read_text(encoding="utf-8")
        for key in ("JWT_SECRET", "RPC_API_KEYS", "CORS_ORIGINS"):
            if f"{key}=change-me" in text or f"{key}=changeme" in text.lower():
                warnings.append(f".env.testnet: rotate {key} before public DNS")
    elif env_example.is_file():
        warnings.append(".env.testnet missing — copy from .env.testnet.example on VPS")
        meta["env_example"] = str(env_example)
    else:
        errors.append("missing:.env.testnet.example")

    bootstrap = ROOT / "scripts" / "vps_testnet_bootstrap.sh"
    if not bootstrap.is_file():
        errors.append("missing:scripts/vps_testnet_bootstrap.sh")
    else:
        meta["bootstrap_script"] = str(bootstrap)

    mesh3_bootstrap = ROOT / "scripts" / "vps_testnet_bootstrap_mesh3.sh"
    if mesh3_bootstrap.is_file():
        meta["bootstrap_mesh3_script"] = str(mesh3_bootstrap)
    else:
        warnings.append("missing:scripts/vps_testnet_bootstrap_mesh3.sh")

    dns_cutover = ROOT / "scripts" / "testnet_dns_cutover.py"
    if dns_cutover.is_file():
        meta["dns_cutover_probe"] = str(dns_cutover)
    else:
        warnings.append("missing:scripts/testnet_dns_cutover.py")

    nginx_install = ROOT / "deploy" / "nginx" / "install_testnet_nginx.sh"
    if nginx_install.is_file():
        meta["nginx_install_script"] = str(nginx_install)
    else:
        warnings.append("missing:deploy/nginx/install_testnet_nginx.sh")

    uptime = ROOT / "scripts" / "testnet_uptime_probe.py"
    if uptime.is_file():
        meta["uptime_probe"] = str(uptime)
    else:
        warnings.append("missing:scripts/testnet_uptime_probe.py")

    meta["ready"] = not errors
    deploy_steps = [
        "cp .env.testnet.example .env.testnet && rotate secrets",
        "./scripts/vps_testnet_bootstrap.sh",
        "sudo bash deploy/nginx/install_testnet_nginx.sh testnet.yourdomain.com",
        "sudo certbot --nginx -d testnet.yourdomain.com",
        "python scripts/testnet_dns_cutover.py --domain testnet.yourdomain.com",
        "python scripts/testnet_uptime_probe.py --append",
        "python scripts/public_testnet_gate.py --live --require-soak-hours 48",
    ]
    if mesh3:
        deploy_steps[1] = "./scripts/vps_testnet_bootstrap_mesh3.sh"
        deploy_steps.append("python scripts/verify_testnet_mesh.py --mesh3 --wait 120")
    meta["deploy_steps"] = deploy_steps

    if domain.strip():
        sys.path.insert(0, str(ROOT / "scripts"))
        import testnet_dns_cutover

        dns_errors, dns_warnings, dns_meta = testnet_dns_cutover.run_testnet_dns_cutover(
            domain=domain.strip(),
            resolve_dns=True,
            check_tls=True,
        )
        meta["dns_cutover"] = dns_meta
        errors.extend([f"dns_cutover:{e}" for e in dns_errors])
        warnings.extend(dns_warnings)

    return errors, warnings, meta


def write_report(errors: list[str], warnings: list[str], meta: dict) -> Path:
    out = ROOT / "logs" / "vps_testnet_preflight.json"
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
    parser = argparse.ArgumentParser(description="VPS public testnet preflight")
    parser.add_argument("--live", action="store_true", help="Probe local testnet seed HTTP")
    parser.add_argument("--base-url", default="http://127.0.0.1:19080")
    parser.add_argument("--mesh3", action="store_true", help="Include 3-node mesh static/live checks")
    parser.add_argument("--domain", default="", help="Optional public hostname HTTPS cutover probe")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings, meta = run_vps_testnet_preflight(
        live=args.live,
        base_url=args.base_url,
        mesh3=args.mesh3,
        domain=args.domain,
    )
    report_path = write_report(errors, warnings, meta)

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "report": str(report_path), **meta}, indent=2))
    else:
        print("=" * 60)
        print("VPS TESTNET PREFLIGHT (chain 77777)")
        print("=" * 60)
        if errors:
            print("RESULT: NOT READY")
            for err in errors:
                print(f"  - {err}")
        else:
            print("RESULT: READY (static)")
        for warn in warnings:
            print(f"  WARN: {warn}")
        print(f"\nReport: {report_path}")
        if not errors:
            print("\nDeploy on VPS:")
            for step in meta.get("deploy_steps") or []:
                print(f"  {step}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
