#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime health checks for the Rust cross-chain bridge CLI."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict, Optional


def l1_rpc_health_required(cfg) -> bool:
    """True when prod bridge must reach real L1 JSON-RPC endpoints."""
    return bool(
        getattr(cfg, "is_production", False)
        and getattr(cfg, "bridge_enabled", False)
        and getattr(cfg, "bridge_require_l1_proof", False)
    )


def should_probe_l1_rpc(cfg=None) -> bool:
    from runtime.env_loader import env_bool

    raw = os.environ.get("BRIDGE_PROBE_L1_RPC")
    if raw is not None and str(raw).strip() != "":
        return env_bool("BRIDGE_PROBE_L1_RPC", False)
    return l1_rpc_health_required(cfg) if cfg is not None else False


def check_l1_rpc_health(cfg=None, timeout: float = 3.0) -> Dict[str, Any]:
    """Report configured L1 RPC URLs and optional live eth_blockNumber probes."""
    from bridge.l1_rpc import configured_l1_rpc_urls, probe_configured_l1_rpcs

    urls = configured_l1_rpc_urls()
    required = l1_rpc_health_required(cfg) if cfg is not None else False
    out: Dict[str, Any] = {
        "required": required,
        "configured": bool(urls),
        "ok": True,
        "error": "",
        "probes": {},
        "endpoints": list(urls.keys()),
        "probed": False,
    }

    if required and not urls:
        out["ok"] = False
        out["error"] = "no L1 RPC URLs configured"
        return out

    if not urls:
        return out

    if not should_probe_l1_rpc(cfg):
        # Configured but not probed — do not claim abs_l1_rpc_ok=1.
        out["ok"] = False
        out["error"] = "probe_skipped"
        return out

    probe = probe_configured_l1_rpcs(timeout=timeout)
    out["probed"] = True
    out["ok"] = bool(probe.get("ok"))
    out["error"] = str(probe.get("error") or "")
    out["probes"] = probe.get("probes") or {}
    return out


def check_rust_bridge_binary(path: str, timeout: float = 3.0) -> Dict[str, Any]:
    """Run a real JSON status smoke-test against abs_bridge_bin."""
    if not path or not os.path.isfile(path):
        return {"ok": False, "error": f"binary missing: {path}", "path": path}

    payload = json.dumps({"command": "status", "args": {}})
    try:
        proc = subprocess.run(
            [path],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except Exception as exc:
        return {"ok": False, "error": f"bridge smoke failed: {exc}", "path": path}

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": f"bridge status exited {proc.returncode}",
            "path": path,
            "stdout": stdout,
            "stderr": stderr,
        }

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "error": f"bridge status returned invalid JSON: {exc}",
            "path": path,
            "stdout": stdout,
            "stderr": stderr,
        }

    status = data.get("status")
    source = str(data.get("source") or "")
    if status not in ("ready", "ok") or "abs_bridge_bin" not in source:
        return {
            "ok": False,
            "error": f"unexpected bridge status response: status={status!r}, source={source!r}",
            "path": path,
            "response": data,
        }

    return {"ok": True, "path": path, "response": data}
