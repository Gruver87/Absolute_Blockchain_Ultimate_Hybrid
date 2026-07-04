#!/usr/bin/env python3
"""E2E prod-profile node boot (isolated ports)."""

import os
import subprocess
import sys
import tempfile
import time
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from runtime.prod_smoke_profile import (
    apply_prod_smoke_env,
    native_available,
    prod_node_config,
)


@pytest.mark.skipif(not native_available(), reason="abs_native wheel required")
def test_prod_node_boots_and_serves_status():
    tmp = tempfile.mkdtemp(prefix="abs_prod_boot_")
    cfg_dict = prod_node_config(
        tmp,
        node_id="boot-1",
        http_port=15280,
        p2p_port=15200,
        rpc_port=15245,
        ws_port=15266,
        bootstrap_peers=[],
        mining_enabled=True,
        bridge_enabled=False,
    )
    cfg_path = os.path.join(tmp, "boot.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        import json
        json.dump(cfg_dict, f)

    env = apply_prod_smoke_env()
    log = os.path.join(tmp, "stderr.log")
    proc = subprocess.Popen(
        [sys.executable, "main.py", "--config", cfg_path],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=open(log, "w", encoding="utf-8"),
    )
    try:
        deadline = time.time() + 120
        ok = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen("http://127.0.0.1:15280/health/live", timeout=3) as resp:
                    if resp.status == 200:
                        ok = True
                        break
            except Exception:
                pass
            time.sleep(2)
        assert ok, f"prod node did not become healthy; see {log}"

        with urllib.request.urlopen("http://127.0.0.1:15280/status", timeout=5) as resp:
            import json
            st = json.loads(resp.read().decode())
        assert st.get("deployment_mode") == "prod"
        assert st.get("bridge_enabled") is False
        assert int(st.get("chain_id", 0)) == cfg_dict["chain_id"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except Exception:
            proc.kill()
