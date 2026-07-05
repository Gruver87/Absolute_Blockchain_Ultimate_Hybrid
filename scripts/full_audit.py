#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FULL AUDIT — единый скрипт полного аудита проекта Absolute Blockchain Ultimate.

Запуск:
    python scripts/full_audit.py
    python scripts/full_audit.py --quick          # без pytest и live-проверок
    python scripts/full_audit.py --live           # + HTTP endpoints (нода должна быть up)
    python scripts/full_audit.py --live --p2p     # + verify_p2p_ci --mode auto (если кластер up)

Отчёт: data/full_audit_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import py_compile
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {
    "_archive", "__pycache__", ".git", "venv", ".venv", "node_modules",
    "backup_20260531_030215", "backups", ".pytest_cache", ".hypothesis",
    "absolute-blockchain-ultimate",
}


@dataclass
class AuditResult:
    name: str
    ok: bool
    critical: int = 0
    warnings: int = 0
    details: List[str] = field(default_factory=list)
    duration_sec: float = 0.0
    skipped: bool = False


def _read(rel: str) -> str:
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8-sig", errors="ignore") as f:
            return f.read()
    except OSError:
        return ""


def _banner(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _run_subprocess(
    cmd: List[str],
    name: str,
    timeout: Optional[int] = None,
) -> AuditResult:
    t0 = time.time()
    res = AuditResult(name=name, ok=True)
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        for line in out.splitlines():
            if line.strip():
                print(line)
        res.ok = proc.returncode == 0
        if not res.ok:
            res.critical = 1
            res.details.append(f"exit_code={proc.returncode}")
    except subprocess.TimeoutExpired as exc:
        res.ok = False
        res.critical = 1
        res.details.append(f"timeout after {timeout}s")
        out = ((exc.stdout or "") + (exc.stderr or "")).strip()
        if out:
            for line in out.splitlines()[-12:]:
                if line.strip():
                    print(line)
        print(f"  [FAIL] {name}: timeout after {timeout}s")
        if "P2P" in name:
            print("  Hint: .\\scripts\\stop_node.ps1  then  .\\scripts\\start_two_nodes.ps1 -Fresh")
            print("  Or increase wait: .\\scripts\\test_full_project.ps1 -Live -P2P -P2PWait 600")
    except Exception as exc:
        res.ok = False
        res.critical = 1
        res.details.append(str(exc))
        print(f"  [FAIL] {name}: {exc}")
    res.duration_sec = time.time() - t0
    return res


def collect_py_files() -> List[str]:
    files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith("backup_")]
        for fn in filenames:
            if fn.endswith(".py") and not fn.startswith("_"):
                rel = os.path.relpath(os.path.join(dirpath, fn), ROOT).replace("\\", "/")
                files.append(rel)
    return sorted(files)


def section_project_inventory() -> AuditResult:
    _banner("[A] PROJECT INVENTORY")
    res = AuditResult(name="inventory", ok=True)
    py_files = collect_py_files()
    http_src = _read("api/http.py")
    main_src = _read("main.py")

    endpoints = set(re.findall(r'path == "(/[^"]+)"', http_src))
    endpoints |= set(re.findall(r'path\.startswith\("(/[^"]+)"\)', http_src))
    endpoints |= set(re.findall(r'path in \(([^)]+)\)', http_src))
    ep_count = len([e for e in endpoints if e.startswith("/")])

    scripts = sorted(
        f.replace("\\", "/")
        for f in os.listdir(os.path.join(ROOT, "scripts"))
        if os.path.isfile(os.path.join(ROOT, "scripts", f))
    )

    print(f"  Python modules     : {len(py_files)}")
    print(f"  REST route refs    : ~{ep_count}")
    print(f"  scripts/ files     : {len(scripts)}")
    print(f"  Entry point        : main.py ({'OK' if os.path.isfile(os.path.join(ROOT, 'main.py')) else 'MISSING'})")
    wave_marker = '"api_wave": 61'
    wave_label = "61" if "reconnect_known_peers" in http_src and wave_marker in http_src else "check"
    print(f"  api_wave in code   : {wave_label}")

    required_scripts = [
        "start_node.ps1", "start_two_nodes.ps1", "docker_devnet.ps1",
        "docker_devnet_3node.ps1", "docker_devnet_5validator.ps1",
        "verify_p2p_ci.py", "mega_audit.py", "final_audit.py", "check_secrets.py",
        "full_audit.py",
    ]
    for s in required_scripts:
        path = os.path.join(ROOT, "scripts", s)
        if not os.path.isfile(path):
            print(f"  [MISS] scripts/{s}")
            res.ok = False
            res.critical += 1
        else:
            print(f"  [OK] scripts/{s}")

    docker_files = [
        "docker-compose.devnet.yml",
        "docker-compose.devnet-rust.yml",
        "docker-compose.devnet-3node.yml",
        "docker-compose.devnet-5validator.yml",
        "docker/founder.wallet.json",
        "docker/validators.devnet5.json",
        "docker/validators.devnet3.json",
    ]
    for df in docker_files:
        ex = os.path.isfile(os.path.join(ROOT, df))
        print(f"  {'[OK]' if ex else '[MISS]'} {df}")
        if not ex:
            res.ok = False
            res.critical += 1

    res.duration_sec = 0
    return res


def section_syntax() -> AuditResult:
    _banner("[B] PYTHON SYNTAX")
    res = AuditResult(name="syntax", ok=True)
    errs: List[str] = []
    for rel in collect_py_files():
        try:
            py_compile.compile(os.path.join(ROOT, rel), doraise=True)
        except py_compile.PyCompileError as exc:
            errs.append(f"{rel}: {exc}")
    if errs:
        res.ok = False
        res.critical = len(errs)
        for e in errs[:20]:
            print(f"  [ERR] {e}")
            res.details.append(e)
        if len(errs) > 20:
            print(f"  ... +{len(errs) - 20} more")
    else:
        print(f"  [OK] {len(collect_py_files())} files syntax-clean")
    return res


def section_waves_52_56() -> AuditResult:
    _banner("[C] WAVES 52–56 (TESTNET / CONSISTENCY / VALIDATORS / PROOF)")
    res = AuditResult(name="waves_52_56", ok=True)
    http_src = _read("api/http.py")
    main_src = _read("main.py")
    checks: List[Tuple[str, bool]] = [
        ("GET /testnet/mesh", '"/testnet/mesh"' in http_src),
        ("GET /testnet/fork-status", '"/testnet/fork-status"' in http_src),
        ("GET /slashing/events", '"/slashing/events"' in http_src or "slashing/events" in http_src),
        ("GET /chain/consistency/harness", '"/chain/consistency/harness"' in http_src),
        ("POST /chain/consistency/repair", '"/chain/consistency/repair"' in http_src),
        ("GET /testnet/validators", '"/testnet/validators"' in http_src),
        ("GET /testnet/multi-node-proof", '"/testnet/multi-node-proof"' in http_src),
        ("POST /testnet/reorg-exercise", '"/testnet/reorg-exercise"' in http_src),
        ("verify_p2p devnet3 mode", "devnet3" in _read("scripts/verify_p2p_ci.py")),
        ("POST /testnet/fork-exercise", '"/testnet/fork-exercise"' in http_src),
        ("unit test wave60", os.path.isfile(os.path.join(ROOT, "tests/unit/test_wave60_bridge_relayer.py"))),
        ("mock l1 rpc", os.path.isfile(os.path.join(ROOT, "bridge/mock_l1_rpc.py"))),
        ("verify_p2p ci-bridge-relayer", "ci-bridge-relayer" in _read("scripts/verify_p2p_ci.py")),
        ("GET /testnet/bridge-relayer-proof", '"/testnet/bridge-relayer-proof"' in http_src),
        ("verify_p2p ci-bridge mode", "ci-bridge" in _read("scripts/verify_p2p_ci.py")),
        ("verify_p2p verify_bridge", "verify_bridge" in _read("scripts/verify_p2p_ci.py")),
        ("bridge enqueue_l1_incoming", "enqueue_l1_incoming" in _read("bridge/abs_bridge.py")),
        ("bridge2 rust path", '"bridge_path": "rust"' in http_src),
        ("unit test bridge relayer e2e", os.path.isfile(os.path.join(ROOT, "tests/unit/test_bridge_relayer_e2e.py"))),
        ("verify_p2p ci-fork mode", "ci-fork" in _read("scripts/verify_p2p_ci.py")),
        ("verify_p2p fork_recovery", "verify_fork_recovery" in _read("scripts/verify_p2p_ci.py")),
        ("verify_p2p devnet5 mode", "devnet5" in _read("scripts/verify_p2p_ci.py")),
        ("verify_p2p ci3 mode", "ci3" in _read("scripts/verify_p2p_ci.py")),
        ("devnet_validators.py", os.path.isfile(os.path.join(ROOT, "runtime/devnet_validators.py"))),
        ("validators.devnet3.json", os.path.isfile(os.path.join(ROOT, "docker/validators.devnet3.json"))),
        ("mining_validator_addresses", "mining_validator_addresses" in _read("runtime/devnet_validators.py")),
        ("ensure_state_at_tip replay fix", "replay_only" in _read("core/blockchain.py")),
        ("seeded dev_signer skip", "Seeded chain" in main_src and "dev_signer skipped" in main_src),
        ("5-validator proposer filter", "mining_validator_addresses" in main_src),
        ("unit test wave52", os.path.isfile(os.path.join(ROOT, "tests/unit/test_wave52_3node_mesh.py"))),
        ("unit test wave53", os.path.isfile(os.path.join(ROOT, "tests/unit/test_wave53_fork_slashing.py"))),
        ("unit test wave54", os.path.isfile(os.path.join(ROOT, "tests/unit/test_wave54_state_consistency.py"))),
        ("unit test wave55", os.path.isfile(os.path.join(ROOT, "tests/unit/test_wave55_5validator.py"))),
        ("unit test wave56", os.path.isfile(os.path.join(ROOT, "tests/unit/test_wave56_multi_node_proof.py"))),
        ("unit test wave58", os.path.isfile(os.path.join(ROOT, "tests/unit/test_wave58_fork_ci.py"))),
        ("deterministic proposer", "abs-proposer:" in _read("consensus_engine.py")),
        ("finality live quorum", "set_active_validator_count" in _read("finality_engine.py")),
        ("reorg finality guard", "finalized floor" in _read("core/blockchain.py")),
    ]
    for name, ok in checks:
        print(f"  {'[OK]' if ok else '[FAIL]'} {name}")
        if not ok:
            res.ok = False
            res.critical += 1
            res.details.append(name)
    return res


def section_tokenomics() -> AuditResult:
    _banner("[D] TOKENOMICS (221M / D.U.P. 17.4%)")
    res = AuditResult(name="tokenomics", ok=True)
    sys.path.insert(0, ROOT)
    try:
        from runtime.tokenomics import (
            MAX_SUPPLY_ABS,
            FOUNDER_AMOUNT_ABS,
            FOUNDER_PERCENT,
            build_allocations,
            genesis_balances,
            get_tokenomics_summary,
        )
        pools = build_allocations()
        pct = sum(p.percent for p in pools)
        summary = get_tokenomics_summary()
        founder_addr = summary["founder"]["address"]
        genesis = genesis_balances(founder_addr)
        checks = [
            ("MAX_SUPPLY=221M", MAX_SUPPLY_ABS == 221_000_000),
            ("Founder%=17.4", abs(FOUNDER_PERCENT - 17.4) < 0.01),
            ("Founder=38,454,000 ABS", abs(FOUNDER_AMOUNT_ABS - 38_454_000) < 1),
            ("Allocations=100%", abs(pct - 100.0) < 0.01),
            ("Founder in genesis", founder_addr in genesis),
        ]
        for name, ok in checks:
            print(f"  {'[OK]' if ok else '[FAIL]'} {name}")
            if not ok:
                res.ok = False
                res.critical += 1
                res.details.append(name)
        print(f"  Founder address: {founder_addr}")
    except Exception as exc:
        res.ok = False
        res.critical += 1
        res.details.append(str(exc))
        print(f"  [FAIL] {exc}")
    return res


def section_node_smoke() -> AuditResult:
    _banner("[E] NODE INIT SMOKE (in-process)")
    res = AuditResult(name="node_smoke", ok=True)
    sys.path.insert(0, ROOT)
    try:
        from main import NodeOrchestrator
        from runtime.config import Config

        n = NodeOrchestrator(Config())
        checks = [
            ("blockchain", n.blockchain is not None),
            ("db", n.db is not None),
            ("p2p", n.p2p is not None),
            ("mempool", n.mempool is not None),
            ("consensus", n.consensus is not None),
            ("pool_locks", n.pool_locks is not None),
            ("height >= 0", n.blockchain.get_height() >= 0),
            ("blockchain.pool_locks linked", n.blockchain.pool_locks is n.pool_locks),
        ]
        for name, ok in checks:
            print(f"  {'[OK]' if ok else '[FAIL]'} {name}")
            if not ok:
                res.ok = False
                res.critical += 1
                res.details.append(name)
    except Exception as exc:
        res.ok = False
        res.critical += 1
        res.details.append(str(exc))
        print(f"  [FAIL] {exc}")
    return res


def _http_get(url: str, timeout: float = 5.0) -> Tuple[bool, Any]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "full_audit/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return True, json.loads(body)
            except json.JSONDecodeError:
                return True, body[:200]
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, str(exc)


def _probe_p2p_height_gap(url1: str, url2: str) -> int:
    """Best-effort height gap between two live nodes (0 if unknown)."""
    try:
        s1 = _http_get(f"{url1}/status", timeout=3.0)
        s2 = _http_get(f"{url2}/status", timeout=3.0)
        if not s1[0] or not s2[0]:
            return 0
        h1 = int((s1[1] or {}).get("height", 0) or 0)
        h2 = int((s2[1] or {}).get("height", 0) or 0)
        return abs(h1 - h2)
    except Exception:
        return 0


def _p2p_subprocess_timeout(wait_sec: int, gap: int) -> int:
    """Subprocess budget: stability wait + bounded preflight catch-up + margin."""
    effective_wait = wait_sec
    if gap > 20:
        effective_wait = max(wait_sec, min(900, gap * 12))
    preflight = 90 if gap <= 20 else min(600, max(120, gap * 8))
    return effective_wait + preflight + 120


def section_p2p_verify(live: bool, base_url: str, wait_sec: int = 300) -> AuditResult:
    """P2P mesh check; with --live and only :8080 up, skip instead of fail."""
    name = "[L] P2P VERIFY (auto cluster)"
    parsed = urlparse(base_url.rstrip("/"))
    host = parsed.hostname or "127.0.0.1"
    scheme = parsed.scheme or "http"
    url1 = f"{scheme}://{host}:8080"
    url2 = f"{scheme}://{host}:8081"
    url3 = f"{scheme}://{host}:8082"

    up1, _ = _http_get(f"{url1}/health/live", timeout=2.0)
    up2, _ = _http_get(f"{url2}/health/live", timeout=2.0)
    up3, _ = _http_get(f"{url3}/health/live", timeout=2.0)

    if live and up1 and not up2 and not up3:
        _banner(name)
        res = AuditResult(name=name, ok=True, skipped=True)
        print("  [SKIP] Single live node on :8080 — mesh P2P needs :8080 + :8081")
        print("         2-node mesh: .\\scripts\\start_two_nodes.ps1  then -Live -P2P")
        print("         Isolated CI P2P: .\\scripts\\test_blockchain_full.ps1 -P2P  (no -Live)")
        res.details = [
            "skipped: only :8080 up with --live",
            "run start_two_nodes.ps1 for mesh P2P",
        ]
        return res

    gap = _probe_p2p_height_gap(url1, url2) if (up1 and up2) else 0
    if gap > 20:
        print(f"  [INFO] P2P height gap={gap} — allow extra catch-up time (or .\\scripts\\start_two_nodes.ps1 -Fresh)")
    subprocess_timeout = _p2p_subprocess_timeout(wait_sec, gap)

    return _run_subprocess(
        [sys.executable, "scripts/verify_p2p_ci.py", "--mode", "auto", "--wait", str(wait_sec)],
        name,
        timeout=subprocess_timeout,
    )


def section_live_endpoints(base: str) -> AuditResult:
    _banner(f"[F] LIVE HTTP ENDPOINTS ({base})")
    res = AuditResult(name="live_endpoints", ok=True)
    paths = [
        "/health/live",
        "/health/ready",
        "/status",
        "/features",
        "/tokenomics",
        "/founder",
        "/peers",
        "/sync/status",
        "/mempool",
        "/chain/metrics",
        "/chain/state-root/status",
        "/chain/consistency/harness",
        "/testnet/mesh",
        "/testnet/fork-status",
        "/testnet/validators",
        "/slashing/events",
        "/openapi.json",
    ]
    up, _ = _http_get(f"{base}/health/live")
    if not up:
        res.skipped = True
        res.warnings += 1
        print(f"  [SKIP] Node not reachable at {base}")
        print("         Start: .\\scripts\\start_node.ps1  or  docker devnet")
        return res

    api_wave = 0
    for path in paths:
        ok, data = _http_get(f"{base}{path}")
        if ok:
            print(f"  [OK] {path}")
            if path == "/status" and isinstance(data, dict):
                api_wave = int(data.get("api_wave", 0) or 0)
                sync = str(data.get("p2p_sync_status", "") or "")
                peers = int(data.get("peers_connected", data.get("peers", 0)) or 0)
                gap = int(data.get("peer_sync_gap", 0) or 0)
                if sync in ("solo", "single_peer_dev"):
                    print(f"  [INFO] P2P mode={sync} — mesh tests need start_two_nodes or docker mesh")
                elif sync == "single_peer_stale":
                    print(
                        f"  [WARN] Stale peer connected (gap={gap}) — "
                        "stop other nodes: .\\scripts\\stop_node.ps1 or docker compose down"
                    )
                    res.warnings += 1
                elif sync in ("under_mesh", "under_mesh_lagging"):
                    need = int(data.get("mesh_min_peers", 2) or 2)
                    print(
                        f"  [WARN] Prod mesh needs >={need} peers (connected={peers}, gap={gap}) — "
                        ".\\scripts\\docker_prod_3node.ps1"
                    )
                    res.warnings += 1
                elif sync == "catching_up":
                    print(f"  [INFO] P2P catching up (gap={gap}) — wait or run sync")
                elif sync == "aligned":
                    print(f"  [OK] P2P aligned (peers={peers})")
        else:
            print(f"  [FAIL] {path} — {data}")
            res.ok = False
            res.critical += 1
            res.details.append(path)

    if api_wave:
        print(f"  api_wave={api_wave} {'(>=61 OK)' if api_wave >= 61 else '(WARN: expected >=61)'}")
        if api_wave < 61:
            res.warnings += 1
    return res


def section_git_hygiene() -> AuditResult:
    _banner("[G] GIT HYGIENE")
    res = AuditResult(name="git_hygiene", ok=True)
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        if not lines:
            print("  [OK] Working tree clean")
        else:
            print(f"  [INFO] {len(lines)} uncommitted changes")
            for ln in lines[:15]:
                print(f"    {ln}")
            if len(lines) > 15:
                print(f"    ... +{len(lines) - 15} more")
    except FileNotFoundError:
        print("  [SKIP] git not installed")
        res.skipped = True
    except Exception as exc:
        print(f"  [WARN] {exc}")
        res.warnings += 1
    return res


def write_report(sections: List[AuditResult], args: argparse.Namespace) -> str:
    out_path = os.path.join(ROOT, "data", "full_audit_report.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    payload: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": "Absolute Blockchain Ultimate",
        "root": ROOT,
        "options": {
            "quick": args.quick,
            "live": args.live,
            "p2p": args.p2p,
            "tests": not args.no_tests,
        },
        "summary": {
            "passed": sum(1 for s in sections if s.ok and not s.skipped),
            "failed": sum(1 for s in sections if not s.ok and not s.skipped),
            "skipped": sum(1 for s in sections if s.skipped),
            "critical_total": sum(s.critical for s in sections),
            "warnings_total": sum(s.warnings for s in sections),
            "overall_ok": all(s.ok or s.skipped for s in sections),
        },
        "sections": [
            {
                "name": s.name,
                "ok": s.ok,
                "skipped": s.skipped,
                "critical": s.critical,
                "warnings": s.warnings,
                "duration_sec": round(s.duration_sec, 2),
                "details": s.details[:50],
            }
            for s in sections
        ],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Full project audit (one script)")
    parser.add_argument("--quick", action="store_true", help="Skip pytest and live checks")
    parser.add_argument("--no-tests", action="store_true", help="Skip pytest only")
    parser.add_argument("--live", action="store_true", help="Probe running node HTTP API")
    parser.add_argument("--p2p", action="store_true", help="Run verify_p2p_ci --mode auto (needs cluster)")
    parser.add_argument("--p2p-wait", type=int, default=300, help="P2P sync wait seconds (verify_p2p_ci --wait)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080", help="Live probe base URL")
    parser.add_argument("--pytest-timeout", type=int, default=600, help="pytest timeout seconds")
    args = parser.parse_args()

    os.chdir(ROOT)
    t_start = time.time()
    sections: List[AuditResult] = []

    print("=" * 72)
    print("FULL AUDIT — ABSOLUTE BLOCKCHAIN ULTIMATE")
    print(f"Root: {ROOT}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    sections.append(section_project_inventory())
    sections.append(section_syntax())
    sections.append(section_waves_52_56())
    sections.append(section_tokenomics())
    sections.append(section_node_smoke())
    sections.append(section_git_hygiene())

    # Subprocess audits
    sections.append(_run_subprocess(
        [sys.executable, "scripts/check_secrets.py"],
        "[H] SECRETS SCAN",
    ))
    sections.append(_run_subprocess(
        [sys.executable, "scripts/mega_audit.py"],
        "[I] MEGA AUDIT (files, endpoints, integration)",
        timeout=300,
    ))
    mega_report = os.path.join(ROOT, "data", "mega_audit_report.json")
    if os.path.isfile(mega_report):
        try:
            with open(mega_report, encoding="utf-8") as f:
                mr = json.load(f)
            mega_issues = mr.get("issues") or []
            if mega_issues:
                sections[-1].ok = False
                sections[-1].critical = len(mega_issues)
                sections[-1].details = [
                    f"{i[0]}: {i[1]}" if isinstance(i, (list, tuple)) else str(i)
                    for i in mega_issues[:20]
                ]
                print(f"  [INFO] mega_audit issues: {len(mega_issues)}")
        except Exception:
            pass

    sections.append(_run_subprocess(
        [sys.executable, "scripts/final_audit.py"],
        "[J] FINAL AUDIT (wiring, pool locks, light client)",
        timeout=300,
    ))

    if not args.no_tests and not args.quick:
        sections.append(_run_subprocess(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line"],
            "[K] PYTEST (full suite)",
            timeout=args.pytest_timeout,
        ))
    else:
        skip = AuditResult(name="pytest", ok=True, skipped=True)
        print("\n[SKIP] pytest (--quick or --no-tests)")
        sections.append(skip)

    if args.live and not args.quick:
        sections.append(section_live_endpoints(args.base_url.rstrip("/")))
    elif not args.quick:
        skip = AuditResult(name="live_endpoints", ok=True, skipped=True)
        print("\n[SKIP] live endpoints (use --live)")
        sections.append(skip)

    if args.p2p and not args.quick:
        sections.append(section_p2p_verify(args.live, args.base_url.rstrip("/"), wait_sec=args.p2p_wait))
    elif args.p2p:
        print("\n[SKIP] P2P verify (--quick active)")

    report_path = write_report(sections, args)
    elapsed = time.time() - t_start
    failed = [s for s in sections if not s.ok and not s.skipped]
    skipped = [s for s in sections if s.skipped]
    passed = [s for s in sections if s.ok and not s.skipped]

    _banner("FULL AUDIT SUMMARY")
    print(f"  Sections passed : {len(passed)}")
    print(f"  Sections failed : {len(failed)}")
    print(f"  Sections skipped: {len(skipped)}")
    print(f"  Critical total  : {sum(s.critical for s in sections)}")
    print(f"  Warnings total  : {sum(s.warnings for s in sections)}")
    print(f"  Elapsed         : {elapsed:.1f}s")
    print(f"  Report          : {report_path}")

    if failed:
        print("\n  FAILED SECTIONS:")
        for s in failed:
            print(f"    - {s.name} (critical={s.critical})")
            for d in s.details[:3]:
                print(f"        {d}")

    overall = len(failed) == 0
    print("\n" + ("  RESULT: OK — project audit passed" if overall else "  RESULT: FAIL — see sections above"))
    print("=" * 72)
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
