#!/usr/bin/env python3
"""Verify P2P wire TLS on prod 3-node mesh (:18180-:18182)."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NODES = (
    "http://127.0.0.1:18180",
    "http://127.0.0.1:18181",
    "http://127.0.0.1:18182",
)
TLS_MESH_ROOT = ROOT / "data" / "p2p_tls_prod_mesh"


def _api(url: str, timeout: float = 10.0) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _probe_ready(base_url: str, timeout: float = 5.0) -> bool:
    try:
        row = _api(f"{base_url.rstrip('/')}/health/ready", timeout=timeout)
        return str(row.get("status", "")).lower() == "ready"
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return False


def check_static_tls_material() -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    meta: dict[str, Any] = {"tls_root": str(TLS_MESH_ROOT)}

    for rel in (
        "scripts/gen_p2p_mesh_tls.py",
        "docker-compose.prod.3node.p2ptls.yml",
        "network/p2p_tls.py",
    ):
        if not (ROOT / rel).is_file():
            errors.append(f"missing:{rel}")

    nodes: list[dict[str, Any]] = []
    for idx in range(1, 4):
        name = f"node{idx}"
        node_dir = TLS_MESH_ROOT / name
        row: dict[str, Any] = {"node": name, "dir": str(node_dir)}
        for fname in ("node.pem", "node.key", "ca.pem"):
            path = node_dir / fname
            row[fname] = path.is_file()
            if not path.is_file():
                errors.append(f"missing TLS file: {node_dir / fname}")
        nodes.append(row)

    ca_pem = TLS_MESH_ROOT / "ca.pem"
    meta["ca_pem"] = ca_pem.is_file()
    if not ca_pem.is_file():
        warnings.append("missing data/p2p_tls_prod_mesh/ca.pem — run: python scripts/gen_p2p_mesh_tls.py")

    meta["nodes"] = nodes
    return errors, warnings, meta


def verify_p2p_tls_mesh(
    *,
    node_urls: list[str] | None = None,
    wait_sec: int = 0,
    check_static: bool = True,
    require_tls: bool = True,
) -> tuple[list[str], list[str], dict[str, Any]]:
    import time

    errors: list[str] = []
    warnings: list[str] = []
    urls = [u.rstrip("/") for u in (node_urls or list(DEFAULT_NODES)) if u]
    meta: dict[str, Any] = {"expected_nodes": len(urls), "require_tls": require_tls}

    if check_static:
        static_errors, static_warnings, static_meta = check_static_tls_material()
        errors.extend(static_errors)
        warnings.extend(static_warnings)
        meta["static"] = static_meta

    deadline = time.time() + max(0, wait_sec)
    reachable: list[str] = []
    while True:
        reachable = [u for u in urls if _probe_ready(u)]
        if len(reachable) == len(urls) or time.time() >= deadline:
            break
        time.sleep(3)

    live_nodes: list[dict[str, Any]] = []
    for i, url in enumerate(urls):
        role = f"node{i + 1}"
        row: dict[str, Any] = {"url": url, "role": role}
        if url not in reachable:
            if require_tls:
                warnings.append(f"{role} not reachable for live TLS probe at {url}")
            live_nodes.append(row)
            continue
        row["reachable"] = True
        try:
            sec = _api(f"{url}/p2p/security", timeout=12)
            tls = sec.get("tls") or {}
            row["tls"] = {
                "enabled": bool(tls.get("enabled")),
                "ready": bool(tls.get("ready")),
                "require_client_cert": bool(tls.get("require_client_cert")),
                "errors": (tls.get("errors") or [])[:3],
            }
            if require_tls:
                if not row["tls"]["enabled"]:
                    errors.append(f"{role} P2P TLS not enabled (start with -P2pTls)")
                elif not row["tls"]["ready"]:
                    errors.append(
                        f"{role} P2P TLS not ready: {(tls.get('errors') or ['unknown'])[:2]}"
                    )
            elif row["tls"]["enabled"] and not row["tls"]["ready"]:
                warnings.append(f"{role} P2P TLS enabled but not ready")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{role} /p2p/security: {exc}")
        live_nodes.append(row)

    if len(reachable) >= 2 and require_tls:
        heights: list[int] = []
        for url in reachable:
            try:
                st = _api(f"{url}/status", timeout=10)
                heights.append(int(st.get("height", 0) or 0))
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
                pass
        if heights and max(heights) - min(heights) > 1:
            warnings.append(f"height spread with TLS mesh: {heights}")

    meta["live_nodes"] = live_nodes
    meta["reachable"] = len(reachable)
    meta["timestamp"] = datetime.now(timezone.utc).isoformat()
    meta["ready"] = not errors
    return errors, warnings, meta


def write_report(errors: list[str], warnings: list[str], meta: dict[str, Any]) -> Path:
    out = ROOT / "logs" / "p2p_tls_mesh_verify.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ok": not errors, "errors": errors, "warnings": warnings, **meta}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify prod mesh P2P wire TLS")
    parser.add_argument("--wait", type=int, default=0, help="Seconds to wait for nodes")
    parser.add_argument("--static-only", action="store_true", help="Check cert files only")
    parser.add_argument("--no-static", action="store_true", help="Skip on-disk cert checks")
    parser.add_argument(
        "--allow-plain",
        action="store_true",
        help="Do not fail when TLS is disabled on running nodes",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.static_only:
        errors, warnings, meta = check_static_tls_material()
        meta["ready"] = not errors
    else:
        errors, warnings, meta = verify_p2p_tls_mesh(
            wait_sec=args.wait,
            check_static=not args.no_static,
            require_tls=not args.allow_plain,
        )

    report = write_report(errors, warnings, meta)

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "report": str(report), **meta}, indent=2))
    else:
        print("=" * 60)
        print("P2P TLS MESH VERIFY (prod :18180-:18182)")
        print("=" * 60)
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
