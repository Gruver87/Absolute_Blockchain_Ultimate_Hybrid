#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-platform two-node P2P smoke test (CI + local)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _api(url: str, timeout: float = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _wait_health(base_url: str, max_sec: int = 120) -> bool:
    for _ in range(max_sec // 3):
        try:
            _api(f"{base_url}/health/live", timeout=5)
            return True
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(3)
    return False


def main() -> int:
    os.chdir(ROOT)
    tmp = tempfile.mkdtemp(prefix="abs_p2p_ci_")
    common = {
        "chain_id": 77777,
        "mining_enabled": False,
        "require_signatures": False,
        "verify_peer_state_root": True,
        "state_root_legacy_cutoff_height": 0,
        "monitor_enabled": False,
        "bridge_enabled": False,
    }
    n1 = {
        **common,
        "node_id": "ci-node-1",
        "p2p_port": 15000,
        "http_port": 15080,
        "rpc_port": 15045,
        "ws_port": 15066,
        "mining_enabled": True,
        "bootstrap_peers": [],
        "db_path": os.path.join(tmp, "node1.db"),
        "log_file": os.path.join(tmp, "node1.log"),
    }
    n2 = {
        **common,
        "node_id": "ci-node-2",
        "p2p_port": 15001,
        "http_port": 15081,
        "rpc_port": 15046,
        "ws_port": 15067,
        "bootstrap_peers": ["127.0.0.1:15000"],
        "db_path": os.path.join(tmp, "node2.db"),
        "log_file": os.path.join(tmp, "node2.log"),
    }

    cfg1 = os.path.join(tmp, "node1.json")
    cfg2 = os.path.join(tmp, "node2.json")
    with open(cfg1, "w", encoding="utf-8") as f:
        json.dump(n1, f)
    with open(cfg2, "w", encoding="utf-8") as f:
        json.dump(n2, f)

    env = os.environ.copy()
    env.pop("TELEGRAM_BOT_TOKEN", None)
    env["MINING_ENABLED"] = ""

    procs = []
    try:
        procs.append(
            subprocess.Popen(
                [sys.executable, "main.py", "--config", cfg1],
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        if not _wait_health("http://127.0.0.1:15080"):
            print("FAIL: node1 health timeout")
            return 1

        procs.append(
            subprocess.Popen(
                [sys.executable, "main.py", "--config", cfg2],
                cwd=ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        )
        if not _wait_health("http://127.0.0.1:15081"):
            print("FAIL: node2 health timeout")
            return 1

        for _ in range(20):
            time.sleep(3)
            try:
                p1 = _api("http://127.0.0.1:15080/peers")
                p2 = _api("http://127.0.0.1:15081/peers")
                if p1.get("count", 0) > 0 or p2.get("count", 0) > 0:
                    break
            except Exception:
                pass
        else:
            print("FAIL: no P2P peers after 60s")
            return 2

        s1 = _api("http://127.0.0.1:15080/status")
        s2 = _api("http://127.0.0.1:15081/status")
        sync2 = _api("http://127.0.0.1:15081/sync/status")
        gap = abs(int(s1.get("height", 0)) - int(s2.get("height", 0)))
        if gap > 50:
            print(f"FAIL: height gap too large ({gap})")
            return 3

        print(
            f"OK: peers n1={p1.get('count', 0)} n2={p2.get('count', 0)} "
            f"heights {s1.get('height')} / {s2.get('height')} "
            f"state_consistent={sync2.get('state_consistent', True)}"
        )
        return 0
    finally:
        for proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=12)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
