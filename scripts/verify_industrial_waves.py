#!/usr/bin/env python3
"""Verify industrial hardening waves v1.3.65–v1.3.71 (plan checklist).

Runs static needle checks, targeted unit tests, and industrial_gate.

Usage (repo root):
  python scripts/verify_industrial_waves.py
  python scripts/verify_industrial_waves.py --skip-gate
  python scripts/verify_industrial_waves.py --json data/verify_industrial_waves.json

Honesty: green here ≠ public mainnet. Ceremony pin / external audit remain org blockers.
Bridge stays OFF on live mesh.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WAVE_TESTS = [
    "tests/unit/test_v1365_fail_closed.py",
    "tests/unit/test_v1366_load_backpressure.py",
    "tests/unit/test_v1367_1368_journal_bridge.py",
    "tests/unit/test_v1369_block_session.py",
    "tests/unit/test_v1370_recursive_native_frames.py",
    "tests/unit/test_v1371_inline_leaf_frame.py",
    "tests/unit/test_v1364_writeback_preload.py",
    "tests/unit/test_v1363_writeback_bundle.py",
    "tests/unit/test_v1362_writeback_commit.py",
    "tests/unit/test_v1361_apply_writeback.py",
]

# (wave, path, must_contain_all)
NEEDLES: list[tuple[str, str, list[str]]] = [
    (
        "1.3.65",
        "crypto/validator_keys.py",
        ["derive_address", "verify_attestation"],
    ),
    (
        "1.3.65",
        "network/p2p_node.py",
        ["validator_register_disabled", "attestation_verifier_unavailable"],
    ),
    (
        "1.3.65",
        "core/blockchain.py",
        ["_native_apply_fail_closed"],
    ),
    (
        "1.3.65",
        "runtime/amount.py",
        ["ABS_REQUIRE_NATIVE_CRYPTO"],
    ),
    (
        "1.3.65",
        "storage/rocks_store.py",
        ["AccountCorruptError"],
    ),
    (
        "1.3.65",
        "api/http.py",
        ["_read_limited_body", "batch too large"],
    ),
    (
        "1.3.66",
        "core/chain_apply_queue.py",
        ["deadline_monotonic", "expired_total"],
    ),
    (
        "1.3.66",
        "network/p2p_node.py",
        [
            "drop mempool txs only after successful import",
            "_schedule_sync",
            "_schedule_connect",
            "_send_q",
        ],
    ),
    (
        "1.3.66",
        "storage/rocks_store.py",
        ['key_meta("chain_tip")', "prefix_last"],
    ),
    (
        "1.3.66",
        "native/abs_native/src/storage/mod.rs",
        ["fn prefix_last"],
    ),
    (
        "1.3.66",
        "observability/metrics.py",
        ["abs_chain_apply_expired_total"],
    ),
    (
        "1.3.67",
        "execution/evm_adapter.py",
        ["begin_writeback_journal", "commit_writeback_journal"],
    ),
    (
        "1.3.67",
        "native/abs_native/src/evm_pure_runner.rs",
        ["Rust-owned storage arena", "fn storage_load(arena:"],
    ),
    (
        "1.3.68",
        "runtime/amount.py",
        ["def try_debit_satoshi"],
    ),
    (
        "1.3.68",
        "storage/rocks_store.py",
        ["try_debit_satoshi"],
    ),
    (
        "1.3.68",
        "bridge/rust_bridge/src/main.rs",
        ["receipt_has_semantic_lock_log", "BRIDGE_L1_LOCK_TOPIC0"],
    ),
    (
        "1.3.69",
        "core/blockchain.py",
        ["block-scoped sat session", "_writeback_accounts_sat(session)"],
    ),
    (
        "1.3.70",
        "native/abs_native/src/evm_pure_runner.rs",
        ["v1.3.70", "re-sync arena after DELEGATECALL"],
    ),
    (
        "1.3.70",
        "execution/evm_adapter.py",
        ["_abs_live_storage"],
    ),
    (
        "1.3.71",
        "runtime/config.py",
        ["1.3.71-industrial"],
    ),
    (
        "1.3.71",
        "native/abs_native/src/evm_pure_runner.rs",
        ["try_inline_leaf_delegate_call", "v1.3.71"],
    ),
]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def check_needles() -> list[str]:
    errors: list[str] = []
    for wave, rel, needles in NEEDLES:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"[{wave}] missing file: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                errors.append(f"[{wave}] {rel}: missing {needle!r}")
    return errors


def check_version() -> list[str]:
    errors: list[str] = []
    try:
        from runtime.config import Config

        ver = str(Config().node_version)
        if not ver.startswith("1.3.71"):
            errors.append(f"node_version expected 1.3.71-*, got {ver}")
    except Exception as exc:
        errors.append(f"config import failed: {exc}")
    return errors


def run_pytest(tests: list[str]) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "pytest", *tests, "-q", "--tb=line"]
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONPATH"] = str(ROOT) + (
        __import__("os").pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return int(proc.returncode), out


def run_industrial_gate() -> tuple[int, str]:
    cmd = [sys.executable, str(ROOT / "scripts" / "industrial_gate.py")]
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONPATH"] = str(ROOT) + (
        __import__("os").pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return int(proc.returncode), out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-gate", action="store_true", help="Skip industrial_gate.py")
    ap.add_argument("--skip-pytest", action="store_true", help="Skip unit tests")
    ap.add_argument(
        "--json",
        default=str(ROOT / "data" / "verify_industrial_waves.json"),
        help="Write JSON report path",
    )
    args = ap.parse_args()

    started = time.time()
    report: dict = {
        "ok": False,
        "node_version": None,
        "needles_ok": False,
        "pytest_rc": None,
        "gate_rc": None,
        "errors": [],
        "warnings": [
            "green ≠ public mainnet",
            "ceremony pin / external audit remain org blockers",
            "keep bridge OFF on live mesh",
        ],
        "elapsed_sec": 0.0,
    }

    print("=== [1/4] Version ===")
    ver_errs = check_version()
    report["errors"].extend(ver_errs)
    try:
        from runtime.config import Config

        report["node_version"] = Config().node_version
        print(f"  node_version={report['node_version']}")
    except Exception as exc:
        print(f"  FAIL: {exc}")

    print("=== [2/4] Static needles (waves 1.3.65–1.3.68) ===")
    needle_errs = check_needles()
    report["errors"].extend(needle_errs)
    report["needles_ok"] = not needle_errs
    if needle_errs:
        for e in needle_errs:
            print(f"  FAIL: {e}")
    else:
        print(f"  OK: {len(NEEDLES)} file checks passed")

    if not args.skip_pytest:
        print("=== [3/4] Unit tests ===")
        missing = [t for t in WAVE_TESTS if not (ROOT / t).is_file()]
        if missing:
            for m in missing:
                report["errors"].append(f"missing test file: {m}")
                print(f"  FAIL: missing {m}")
        rc, out = run_pytest([t for t in WAVE_TESTS if (ROOT / t).is_file()])
        report["pytest_rc"] = rc
        if rc != 0:
            report["errors"].append("pytest failed")
            print(out[-2000:] if len(out) > 2000 else out)
            print(f"  FAIL: pytest rc={rc}")
        else:
            # last non-empty line often has passed count
            tail = [ln for ln in out.strip().splitlines() if ln.strip()][-3:]
            for ln in tail:
                print(f"  {ln}")
            print(f"  OK: pytest rc=0")
    else:
        print("=== [3/4] Unit tests SKIPPED ===")

    if not args.skip_gate:
        print("=== [4/4] industrial_gate ===")
        rc, out = run_industrial_gate()
        report["gate_rc"] = rc
        # Show last summary lines
        lines = [ln for ln in out.splitlines() if ln.strip()]
        for ln in lines[-12:]:
            print(f"  {ln}")
        if rc != 0:
            report["errors"].append("industrial_gate failed")
            print(f"  FAIL: gate rc={rc}")
        else:
            print("  OK: industrial_gate")
    else:
        print("=== [4/4] industrial_gate SKIPPED ===")

    report["elapsed_sec"] = round(time.time() - started, 3)
    report["ok"] = len(report["errors"]) == 0 and (
        args.skip_pytest or report["pytest_rc"] == 0
    ) and (args.skip_gate or report["gate_rc"] == 0)

    out_path = Path(args.json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print()
    if report["ok"]:
        print(f"PASS: industrial waves verify OK ({report['elapsed_sec']}s)")
        print(f"  report: {out_path}")
        return 0
    print(f"FAIL: {len(report['errors'])} error(s) ({report['elapsed_sec']}s)")
    for e in report["errors"]:
        print(f"  - {e}")
    print(f"  report: {out_path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
