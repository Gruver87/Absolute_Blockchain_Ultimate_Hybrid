#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-platform two-node P2P smoke test.

Modes (default: auto):
  auto   — if :8080/:8081 are up, verify running devnet; else spawn isolated CI nodes
  devnet — verify already running nodes (start_two_nodes.ps1 → :8080 / :8081)
  ci     — spawn temporary nodes on :15080 / :15081 (GitHub Actions, no devnet needed)

After start_two_nodes.ps1 use either:
  .\\scripts\\verify_p2p.ps1
  python scripts/verify_p2p_ci.py
  python scripts/verify_p2p_ci.py --mode devnet
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEVNET_URL1 = "http://127.0.0.1:8080"
DEVNET_URL2 = "http://127.0.0.1:8081"


def _api(url: str, timeout: float = 10) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _probe_health(base_url: str, timeout: float = 2) -> bool:
    try:
        _api(f"{base_url}/health/live", timeout=timeout)
        return True
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return False


def _wait_health(base_url: str, max_sec: int = 120) -> bool:
    for _ in range(max_sec // 3):
        if _probe_health(base_url, timeout=5):
            return True
        time.sleep(3)
    return False


def _post_json(base_url: str, path: str, body: dict | None = None, timeout: float = 15) -> dict:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _trigger_catchup(url1: str, url2: str, s1: dict, s2: dict) -> None:
    """Schedule P2P catch-up on the lagging node."""
    h1 = int(s1.get("height", 0) or 0)
    h2 = int(s2.get("height", 0) or 0)
    try:
        if h2 < h1:
            _post_json(url2, "/sync/fast-sync")
        elif h1 < h2:
            _post_json(url1, "/sync/fast-sync")
    except Exception:
        pass


def _trigger_reconcile(url1: str, url2: str) -> None:
    """Ask both nodes to align forks and state roots."""
    for url in (url1, url2):
        try:
            _post_json(url, "/sync/reconcile")
            _post_json(url, "/sync/fast-sync")
        except Exception:
            pass


def verify_pair(url1: str, url2: str, wait_sync_sec: int = 240) -> int:
    """Check peers, height sync, attestations on two running nodes."""
    if not _probe_health(url1):
        print(f"FAIL: node1 not reachable at {url1}")
        print("  Start devnet: .\\scripts\\start_two_nodes.ps1")
        return 1
    if not _probe_health(url2):
        print(f"FAIL: node2 not reachable at {url2}")
        print("  Node2 is down. Restart both nodes:")
        print("    .\\scripts\\stop_node.ps1")
        print("    .\\scripts\\start_two_nodes.ps1")
        return 1

    try:
        s1 = _api(f"{url1}/status")
        s2 = _api(f"{url2}/status")
    except Exception as exc:
        print(f"FAIL: cannot read /status: {exc}")
        return 1

    cid1, cid2 = s1.get("chain_id"), s2.get("chain_id")
    if cid1 != cid2:
        print(f"FAIL: chain_id mismatch node1={cid1} node2={cid2}")
        print("  Nodes cannot handshake — stop stray processes and restart:")
        print("    .\\scripts\\stop_node.ps1")
        print("    .\\scripts\\start_two_nodes.ps1")
        print("  Always use --config node.example.json / node2.example.json")
        return 4

    loops = max(20, wait_sync_sec // 3)
    p1 = p2 = {}
    stable_ok = 0
    STABLE_NEED = 3
    MAX_MINING_GAP = 2  # node1 mines while node2 catches up
    for i in range(loops):
        try:
            p1 = _api(f"{url1}/peers")
            p2 = _api(f"{url2}/peers")
            s1 = _api(f"{url1}/status")
            s2 = _api(f"{url2}/status")
            sync1 = _api(f"{url1}/sync/status")
            sync2 = _api(f"{url2}/sync/status")
            gap = abs(int(s1.get("height", 0)) - int(s2.get("height", 0)))
            c1 = int(p1.get("count", 0) or 0)
            c2 = int(p2.get("count", 0) or 0)
            root1 = (sync1.get("state_root") or s1.get("state_root") or "").lower()
            root2 = (sync2.get("state_root") or s2.get("state_root") or "").lower()
            roots_match = bool(root1 and root2 and root1 == root2)
            both_peered = c1 > 0 and c2 > 0

            if both_peered and gap <= MAX_MINING_GAP and roots_match:
                stable_ok += 1
                if stable_ok >= STABLE_NEED:
                    break
            else:
                stable_ok = 0
                if both_peered or c1 > 0 or c2 > 0:
                    if gap > 0:
                        lag_url = url2 if int(s1.get("height", 0)) > int(s2.get("height", 0)) else url1
                        try:
                            _post_json(lag_url, "/sync/reconcile", timeout=120)
                        except Exception:
                            _trigger_catchup(url1, url2, s1, s2)
                    elif not roots_match:
                        _trigger_reconcile(url1, url2)
        except Exception:
            stable_ok = 0
        time.sleep(3)
    else:
        print(f"FAIL: no stable P2P sync after {wait_sync_sec}s")
        print(f"  chain_id={cid1} node1 peers={p1.get('count', '?')} height={s1.get('height', '?')}")
        print(f"  chain_id={cid2} node2 peers={p2.get('count', '?')} height={s2.get('height', '?')}")
        try:
            sync1 = _api(f"{url1}/sync/status")
            sync2 = _api(f"{url2}/sync/status")
            print(
                f"  state_roots node1={str(sync1.get('state_root', ''))[:16]} "
                f"node2={str(sync2.get('state_root', ''))[:16]} "
                f"peer_sync_gap={s1.get('peer_sync_gap', '?')}"
            )
        except Exception:
            pass
        if p1.get("count", 0) > 0 or p2.get("count", 0) > 0:
            print("  Peers linked but heights/state diverged - try:")
            print("    Invoke-RestMethod http://127.0.0.1:8081/sync/reconcile -Method POST -Body '{}' -ContentType 'application/json'")
            print("    Invoke-RestMethod http://127.0.0.1:8081/sync/fast-sync -Method POST -Body '{}' -ContentType 'application/json'")
        print("  Or: .\\scripts\\stop_node.ps1  then  .\\scripts\\docker_devnet.ps1 -RustBridge")
        return 2

    sync1 = _api(f"{url1}/sync/status")
    sync2 = _api(f"{url2}/sync/status")
    att1 = _api(f"{url1}/consensus/attestations")
    gap = abs(int(s1.get("height", 0)) - int(s2.get("height", 0)))
    if gap > 50:
        print(f"FAIL: height gap too large ({gap})")
        return 3

    root1 = (sync1.get("state_root") or s1.get("state_root") or "").lower()
    root2 = (sync2.get("state_root") or s2.get("state_root") or "").lower()
    consistent = sync1.get("state_consistent", True) and sync2.get("state_consistent", True)
    roots_match = bool(root1 and root2 and root1 == root2)

    print(
        f"OK: peers n1={p1.get('count', 0)} n2={p2.get('count', 0)} "
        f"heights {s1.get('height')} / {s2.get('height')} "
        f"nodes {s1.get('node_id', '?')} / {s2.get('node_id', '?')} "
        f"attestations={att1.get('count', 0)} "
        f"state_consistent={consistent} state_roots_match={roots_match}"
    )
    if s1.get("node_id", "").startswith("node-") and not s1.get("node_id", "").startswith("docker-"):
        print("WARN: :8080/:8081 answer local nodes — stop them: .\\scripts\\stop_node.ps1")
    if gap > 0:
        print(f"WARN: height gap {gap} — lagging node still catching up")
        return 6
    if gap == 0 and not roots_match:
        print("WARN: same height but state_root differs — re-run docker_devnet or start_two_nodes.ps1")
        print("  Tip: Invoke-RestMethod http://127.0.0.1:8081/sync/reconcile -Method POST -Body '{}' -ContentType 'application/json'")
        return 5
    return 0


def run_ci_spawn() -> int:
    """Isolated two-node test on high ports (does not touch devnet :8080)."""
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

    log1 = os.path.join(tmp, "node1.stderr.log")
    log2 = os.path.join(tmp, "node2.stderr.log")
    procs = []
    try:
        print(f"CI mode: spawning isolated nodes on :15080 / :15081 (tmp={tmp})")
        with open(log1, "w", encoding="utf-8") as err1:
            procs.append(
                subprocess.Popen(
                    [sys.executable, "main.py", "--config", cfg1],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=err1,
                )
            )
        if not _wait_health("http://127.0.0.1:15080"):
            print("FAIL: node1 health timeout on :15080")
            print(f"  stderr: {log1}")
            return 1

        with open(log2, "w", encoding="utf-8") as err2:
            procs.append(
                subprocess.Popen(
                    [sys.executable, "main.py", "--config", cfg2],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=err2,
                )
            )
        if not _wait_health("http://127.0.0.1:15081"):
            print("FAIL: node2 health timeout on :15081")
            print(f"  stderr: {log2}")
            return 1

        return verify_pair("http://127.0.0.1:15080", "http://127.0.0.1:15081")
    finally:
        for proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=12)
            except Exception:
                proc.kill()


def main() -> int:
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description="Two-node P2P verification")
    parser.add_argument(
        "--mode",
        choices=("auto", "devnet", "ci"),
        default="auto",
        help="auto=detect running devnet; devnet=:8080/:8081; ci=isolated spawn",
    )
    parser.add_argument("--url1", default=DEVNET_URL1, help="node1 REST base URL")
    parser.add_argument("--url2", default=DEVNET_URL2, help="node2 REST base URL")
    parser.add_argument(
        "--wait",
        type=int,
        default=240,
        help="seconds to wait for stable P2P sync (devnet mode)",
    )
    args = parser.parse_args()

    mode = args.mode
    if mode == "auto":
        up1 = _probe_health(args.url1)
        up2 = _probe_health(args.url2)
        if up1 and up2:
            mode = "devnet"
            print(f"Auto: devnet detected at {args.url1} and {args.url2}")
        elif up1 or up2:
            print("FAIL: only one devnet node is running")
            if up1:
                try:
                    s = _api(f"{args.url1}/status", timeout=3)
                    print(f"  node1 UP  :8080 chain_id={s.get('chain_id')} height={s.get('height')}")
                except Exception:
                    print("  node1 UP  :8080")
            else:
                print("  node1 DOWN :8080")
            if up2:
                try:
                    s = _api(f"{args.url2}/status", timeout=3)
                    print(f"  node2 UP  :8081 chain_id={s.get('chain_id')} height={s.get('height')}")
                except Exception:
                    print("  node2 UP  :8081")
            else:
                print("  node2 DOWN :8081")
            print("  Fix: .\\scripts\\stop_node.ps1  then  .\\scripts\\start_two_nodes.ps1")
            return 1
        else:
            mode = "ci"
            print("Auto: no devnet on :8080/:8081 — running isolated CI test (--mode ci)")

    if mode == "devnet":
        print(f"Devnet mode: checking {args.url1} and {args.url2}")
        return verify_pair(args.url1, args.url2, wait_sync_sec=args.wait)

    return run_ci_spawn()


if __name__ == "__main__":
    sys.exit(main())
