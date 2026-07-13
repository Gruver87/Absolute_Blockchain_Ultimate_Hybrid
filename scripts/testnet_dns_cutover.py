#!/usr/bin/env python3
"""Probe public testnet DNS + HTTPS cutover (nginx /api in front of seed)."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHAIN_ID = 77777


def _normalize_domain(domain: str) -> str:
    raw = str(domain or "").strip().lower()
    if raw.startswith("https://"):
        raw = raw[8:]
    elif raw.startswith("http://"):
        raw = raw[7:]
    return raw.split("/")[0].strip()


def _api_base(domain: str, api_prefix: str) -> str:
    host = _normalize_domain(domain)
    prefix = api_prefix.strip() or "/api"
    if not prefix.startswith("/"):
        prefix = f"/{prefix}"
    return f"https://{host}{prefix.rstrip('/')}"


def _resolve_dns(domain: str) -> tuple[list[str], str | None]:
    host = _normalize_domain(domain)
    try:
        rows = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        return [], str(exc)
    addrs = sorted({row[4][0] for row in rows})
    return addrs, None


def _tls_summary(domain: str, timeout: float = 10.0) -> tuple[dict[str, Any], str | None]:
    host = _normalize_domain(domain)
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert() or {}
                not_after = cert.get("notAfter", "")
                issuer = cert.get("issuer", ())
                issuer_cn = ""
                for item in issuer:
                    if item and item[0] == "commonName":
                        issuer_cn = str(item[1])
                        break
                return {
                    "subject": cert.get("subject"),
                    "issuer_cn": issuer_cn,
                    "not_after": not_after,
                    "version": ssock.version(),
                }, None
    except (OSError, ssl.SSLError) as exc:
        return {}, str(exc)


def _get_json(url: str, timeout: float = 12.0) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def run_testnet_dns_cutover(
    *,
    domain: str,
    api_prefix: str = "/api",
    resolve_dns: bool = True,
    check_tls: bool = True,
    timeout: float = 12.0,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    host = _normalize_domain(domain)
    base = _api_base(domain, api_prefix)
    meta: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": host,
        "api_base": base,
        "chain_id_expected": EXPECTED_CHAIN_ID,
    }

    if not host or "." not in host:
        errors.append(f"invalid domain: {domain!r}")
        meta["ready"] = False
        return errors, warnings, meta

    if resolve_dns:
        addrs, dns_err = _resolve_dns(host)
        meta["dns_addresses"] = addrs
        if dns_err:
            errors.append(f"dns:{dns_err}")
        elif not addrs:
            errors.append(f"dns:no A/AAAA records for {host}")

    if check_tls:
        tls_meta, tls_err = _tls_summary(host, timeout=timeout)
        meta["tls"] = tls_meta
        if tls_err:
            errors.append(f"tls:{tls_err}")
        elif tls_meta.get("not_after"):
            warnings.append(f"tls: cert expires {tls_meta['not_after']}")

    try:
        ready = _get_json(f"{base}/health/ready", timeout=timeout)
        meta["ready_payload"] = ready
        if str(ready.get("status", "")).lower() != "ready":
            errors.append(f"health/ready status={ready.get('status')!r}")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"health/ready: {exc}")

    if not errors:
        try:
            status = _get_json(f"{base}/status", timeout=timeout)
            meta["status"] = {
                "chain_id": status.get("chain_id"),
                "height": status.get("height"),
                "peers": status.get("peers", status.get("peer_count")),
            }
            chain_id = int(status.get("chain_id", 0) or 0)
            if chain_id != EXPECTED_CHAIN_ID:
                errors.append(f"chain_id={chain_id} expected {EXPECTED_CHAIN_ID}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"status: {exc}")

    if not errors:
        try:
            harness = _get_json(
                f"{base}/chain/consistency/harness?quick=1&peer_timeout=5",
                timeout=max(timeout, 25.0),
            )
            meta["harness"] = {
                "harness_healthy": harness.get("harness_healthy"),
                "tip_state_aligned": harness.get("tip_state_aligned"),
            }
            if not harness.get("harness_healthy"):
                errors.append("harness not healthy")
            if not harness.get("tip_state_aligned"):
                errors.append("tip_state not aligned")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            warnings.append(f"harness: {exc}")

    meta["ready"] = not errors
    return errors, warnings, meta


def write_report(errors: list[str], warnings: list[str], meta: dict[str, Any]) -> Path:
    out = ROOT / "logs" / "testnet_dns_cutover.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ok": not errors, "errors": errors, "warnings": warnings, **meta}
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Public testnet DNS + HTTPS cutover probe")
    parser.add_argument("--domain", required=True, help="Public hostname (e.g. testnet.example.com)")
    parser.add_argument("--api-prefix", default="/api", help="nginx API prefix (default /api)")
    parser.add_argument("--no-dns", action="store_true", help="Skip DNS resolution check")
    parser.add_argument("--no-tls", action="store_true", help="Skip TLS certificate handshake check")
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings, meta = run_testnet_dns_cutover(
        domain=args.domain,
        api_prefix=args.api_prefix,
        resolve_dns=not args.no_dns,
        check_tls=not args.no_tls,
        timeout=args.timeout,
    )
    report = write_report(errors, warnings, meta)

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings, "report": str(report), **meta}, indent=2))
    else:
        print("=" * 60)
        print(f"TESTNET DNS CUTOVER ({meta.get('domain')})")
        print("=" * 60)
        if errors:
            print("RESULT: FAIL")
            for err in errors:
                print(f"  - {err}")
        else:
            print("RESULT: OK")
        for warn in warnings:
            print(f"  WARN: {warn}")
        if meta.get("dns_addresses"):
            print(f"  DNS: {', '.join(meta['dns_addresses'])}")
        print(f"Report: {report}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
