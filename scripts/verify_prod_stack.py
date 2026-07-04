#!/usr/bin/env python3
"""Production stack readiness checks (static + optional live smoke)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check_prod_gate() -> list[str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "prod_gate.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return [proc.stdout.strip() or proc.stderr.strip() or "prod_gate failed"]
    return []


def check_config_validate() -> list[str]:
    from runtime.config import Config

    path = ROOT / "node.prod.example.json"
    placeholders = {
        "JWT_SECRET": "Q" * 40,
        "RPC_API_KEYS": "R" * 40,
        "BRIDGE_ORACLE_SECRET": "S" * 40,
        "ETH_RPC_URL": "https://rpc.example.com",
        "CORS_ORIGINS": "https://explorer.example.com",
        "BRIDGE_PROBE_L1_RPC": "false",
    }
    saved = {key: os.environ.get(key) for key in placeholders}
    try:
        for key, value in placeholders.items():
            os.environ[key] = value
        cfg = Config.from_json(str(path))
        cfg.apply_env()
        errors = cfg.validate()
        bridge_candidates = [
            ROOT / "bridge" / "abs_bridge_bin.exe",
            ROOT / "bridge" / "abs_bridge_bin",
        ]
        if not any(p.is_file() for p in bridge_candidates):
            errors = [e for e in errors if "rust binary smoke-test" not in e]
        return errors
    finally:
        for key, old in saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old


def check_docker_prod_compose() -> list[str]:
    compose = ROOT / "docker-compose.prod.yml"
    text = compose.read_text(encoding="utf-8")
    errors: list[str] = []
    for needle in ("relayer:", "BRIDGE_REQUIRE_L1_PROOF", "ABS_REQUIRE_NATIVE_CRYPTO"):
        if needle not in text:
            errors.append(f"docker-compose.prod.yml missing {needle}")
    compose_env = {
        "JWT_SECRET": "Q" * 40,
        "RPC_API_KEYS": "R" * 40,
        "BRIDGE_ORACLE_SECRET": "S" * 40,
        "ETH_RPC_URL": "https://rpc.example.com",
        "CORS_ORIGINS": "https://explorer.example.com",
    }
    saved = {key: os.environ.get(key) for key in compose_env}
    try:
        os.environ.update(compose_env)
        proc = subprocess.run(
            ["docker", "compose", "-f", str(compose), "config", "--quiet"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            errors.append(proc.stderr.strip() or "docker compose config failed")
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        errors.append("docker compose config timed out")
    finally:
        for key, old in saved.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
    return errors


def check_live_smoke(base: str) -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import prod_smoke

    report = prod_smoke.run_prod_smoke(base)
    return list(report.get("errors") or [])


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify production stack readiness")
    parser.add_argument("--live", action="store_true", help="Also run prod_smoke against running node")
    parser.add_argument("--base-url", default=os.getenv("ABS_API_URL", "http://127.0.0.1:8080"))
    args = parser.parse_args()

    errors: list[str] = []
    errors.extend(check_prod_gate())
    errors.extend(check_config_validate())
    errors.extend(check_docker_prod_compose())
    if args.live:
        errors.extend(check_live_smoke(args.base_url.rstrip("/")))

    if errors:
        print("FAIL: production stack verification")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("OK: production stack verification")
    if args.live:
        print(f"  live smoke: {args.base_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
