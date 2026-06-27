#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime health checks for the Rust cross-chain bridge CLI."""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Dict


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
