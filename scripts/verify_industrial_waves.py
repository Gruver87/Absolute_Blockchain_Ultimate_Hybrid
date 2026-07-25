#!/usr/bin/env python3
"""Verify industrial hardening waves v1.3.65–v1.3.94 (plan checklist).

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
    "tests/unit/test_v1372_p2p_admission.py",
    "tests/unit/test_v1373_apply_priority.py",
    "tests/unit/test_v1374_value0_call.py",
    "tests/unit/test_v1375_multidepth_call.py",
    "tests/unit/test_v1376_value_call.py",
    "tests/unit/test_v1377_p2p_ingress.py",
    "tests/unit/test_v1378_p2p_bandwidth.py",
    "tests/unit/test_v1379_callcode_value.py",
    "tests/unit/test_v1380_simple_create.py",
    "tests/unit/test_v1381_create2.py",
    "tests/unit/test_v1382_create_runtime.py",
    "tests/unit/test_v1383_writeback_journal.py",
    "tests/unit/test_v1384_create_writeback.py",
    "tests/unit/test_v1385_p2p_egress.py",
    "tests/unit/test_v1386_p2p_framer.py",
    "tests/unit/test_v1387_p2p_egress_prepare.py",
    "tests/unit/test_v1388_native_fuzz.py",
    "tests/unit/test_v1389_p2p_sybil_eclipse.py",
    "tests/unit/test_v1390_p2p_native_transport.py",
    "tests/unit/test_v1391_p2p_native_tls.py",
    "tests/unit/test_v1392_p2p_native_read_message.py",
    "tests/unit/test_v1393_p2p_native_write_message.py",
    "tests/unit/test_v1394_p2p_native_read_messages.py",
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
        "native/abs_native/src/evm_pure_runner.rs",
        ["try_inline_leaf_delegate_call", "v1.3.71"],
    ),
    (
        "1.3.72",
        "runtime/config.py",
        ["p2p_max_sync_inflight", "p2p_exempt_messages_per_sec"],
    ),
    (
        "1.3.72",
        "network/p2p_node.py",
        ["sync admission reject", "_bump_outbound_drop", "_exempt_rate_ok"],
    ),
    (
        "1.3.72",
        "observability/metrics.py",
        ["abs_p2p_outbound_drops_total", "abs_p2p_sync_admission_rejects_total"],
    ),
    (
        "1.3.73",
        "core/chain_apply_queue.py",
        ["PriorityQueue", "_APPLY_PRIORITY", "v1.3.73"],
    ),
    (
        "1.3.73",
        "observability/metrics.py",
        ["abs_chain_apply_error_total", "abs_chain_apply_priority_lanes"],
    ),
    (
        "1.3.74",
        "native/abs_native/src/evm_pure_runner.rs",
        ["try_inline_leaf_value0_call", "v1.3.74"],
    ),
    (
        "1.3.75",
        "native/abs_native/src/evm_pure_runner.rs",
        [
            "bytecode_is_inline_call_frame_eligible",
            "MAX_INLINE_CALL_DEPTH",
            "_abs_inline_depth",
        ],
    ),
    (
        "1.3.76",
        "RELEASE_NOTES_v1.3.76.md",
        ["1.3.76-industrial", "fail-closed"],
    ),
    (
        "1.3.76",
        "native/abs_native/src/evm_pure_runner.rs",
        ["try_inline_value_transfer", "InlineValueTransfer", "v1.3.76"],
    ),
    (
        "1.3.77",
        "RELEASE_NOTES_v1.3.77.md",
        ["1.3.77-industrial", "p2p_ingress_admit"],
    ),
    (
        "1.3.77",
        "native/abs_native/src/p2p_ingress.rs",
        ["p2p_ingress_admit", "P2PConnectionGovernor"],
    ),
    (
        "1.3.77",
        "network/p2p_node.py",
        ["p2p_ingress_admit", "_use_native_ingress", "P2PConnectionGovernor"],
    ),
    (
        "1.3.78",
        "RELEASE_NOTES_v1.3.78.md",
        ["1.3.78-industrial", "bandwidth"],
    ),
    (
        "1.3.78",
        "native/abs_native/src/p2p_rate_limit.rs",
        ["bandwidth_exceeded", "ingress_cost_units", "byte_limit"],
    ),
    (
        "1.3.78",
        "observability/metrics.py",
        ["abs_p2p_bandwidth_rejects_total"],
    ),
    (
        "1.3.79",
        "RELEASE_NOTES_v1.3.79.md",
        ["1.3.79-industrial", "CALLCODE"],
    ),
    (
        "1.3.79",
        "native/abs_native/src/evm_pure_runner.rs",
        ["native_inline_callcode_value", "v1.3.79"],
    ),
    (
        "1.3.80",
        "RELEASE_NOTES_v1.3.80.md",
        ["1.3.80-industrial", "CREATE"],
    ),
    (
        "1.3.80",
        "native/abs_native/src/evm_pure_runner.rs",
        ["try_inline_simple_create", "native_inline_simple_create", "v1.3.80"],
    ),
    (
        "1.3.81",
        "RELEASE_NOTES_v1.3.81.md",
        ["1.3.81-industrial", "CREATE2"],
    ),
    (
        "1.3.81",
        "native/abs_native/src/evm_pure_runner.rs",
        ["native_inline_create2", "create2_eip1014_enabled", "v1.3.81"],
    ),
    (
        "1.3.82",
        "RELEASE_NOTES_v1.3.82.md",
        ["1.3.82-industrial"],
    ),
    (
        "1.3.82",
        "native/abs_native/src/evm_pure_runner.rs",
        ["run_inline_create_init", "native_inline_create_runtime", "v1.3.82"],
    ),
    (
        "1.3.83",
        "RELEASE_NOTES_v1.3.83.md",
        ["1.3.83-industrial"],
    ),
    (
        "1.3.83",
        "native/abs_native/src/evm_pure_runner.rs",
        [
            "push_pending_writeback_transfer",
            "pending_writeback_ops",
            "native_inline_writeback_value",
            "v1.3.83",
        ],
    ),
    (
        "1.3.83",
        "execution/evm_adapter.py",
        ["_take_bridge_pending_writeback", "native_inline_writeback"],
    ),
    (
        "1.3.84",
        "RELEASE_NOTES_v1.3.84.md",
        ["1.3.84-industrial"],
    ),
    (
        "1.3.84",
        "native/abs_native/src/evm_pure_runner.rs",
        [
            "push_pending_writeback_save_account",
            "native_inline_writeback_create",
            "v1.3.84",
        ],
    ),
    (
        "1.3.85",
        "RELEASE_NOTES_v1.3.85.md",
        ["1.3.85-industrial"],
    ),
    (
        "1.3.85",
        "native/abs_native/src/p2p_rate_limit.rs",
        [
            "admit_egress",
            "egress_bandwidth_exceeded",
            "p2p_egress_admit",
            "v1.3.85",
        ],
    ),
    (
        "1.3.85",
        "observability/metrics.py",
        ["abs_p2p_egress_rejects_total"],
    ),
    (
        "1.3.86",
        "RELEASE_NOTES_v1.3.86.md",
        ["1.3.86-industrial"],
    ),
    (
        "1.3.86",
        "native/abs_native/src/p2p_frame.rs",
        ["P2PLineFramer", "p2p_line_too_large", "v1.3.86"],
    ),
    (
        "1.3.86",
        "network/p2p_node.py",
        ["_read_wire_line", "P2PLineFramer"],
    ),
    (
        "1.3.87",
        "RELEASE_NOTES_v1.3.87.md",
        ["1.3.87-industrial"],
    ),
    (
        "1.3.87",
        "native/abs_native/src/p2p_ingress.rs",
        ["p2p_egress_prepare", "v1.3.87"],
    ),
    (
        "1.3.87",
        "network/p2p_node.py",
        ["_prepare_outbound", "p2p_egress_prepare"],
    ),
    (
        "1.3.88",
        "RELEASE_NOTES_v1.3.88.md",
        ["1.3.88-industrial"],
    ),
    (
        "1.3.88",
        "native/abs_native/src/fuzz_api.rs",
        ["fuzz_p2p_frame_feed", "fuzz_p2p_wire_parse", "fuzz_p2p_rate_limit_sequence"],
    ),
    (
        "1.3.88",
        "scripts/fuzz_native.ps1",
        ["fuzz_p2p_", "cargo fuzz"],
    ),
    (
        "1.3.88",
        ".github/workflows/fuzz-native.yml",
        ["cargo fuzz run", "fuzz_p2p_"],
    ),
    (
        "1.3.89",
        "RELEASE_NOTES_v1.3.89.md",
        ["1.3.89-industrial"],
    ),
    (
        "1.3.89",
        "native/abs_native/src/p2p_ingress.rs",
        ["p2p_subnet_key", "reserved_outbound_slots", "v1.3.89"],
    ),
    (
        "1.3.89",
        "network/p2p_node.py",
        ["_maybe_eclipse_prune", "diversity_snapshot"],
    ),
    (
        "1.3.89",
        "observability/metrics.py",
        ["abs_p2p_subnet_rejects_total", "abs_p2p_eclipse_at_risk"],
    ),
    (
        "1.3.90",
        "RELEASE_NOTES_v1.3.90.md",
        ["1.3.90-industrial"],
    ),
    (
        "1.3.90",
        "native/abs_native/src/p2p_transport.rs",
        ["P2PNativeListener", "P2PNativeConn", "v1.3.90"],
    ),
    (
        "1.3.90",
        "network/p2p_node.py",
        ["_native_accept_loop", "_handle_native_incoming"],
    ),
    (
        "1.3.91",
        "RELEASE_NOTES_v1.3.91.md",
        ["1.3.91-industrial"],
    ),
    (
        "1.3.91",
        "native/abs_native/src/p2p_transport.rs",
        ["rustls", "p2p_native_tls_available", "WebPkiClientVerifier"],
    ),
    (
        "1.3.91",
        "network/p2p_node.py",
        ["_native_tls", "native-tls"],
    ),
    (
        "1.3.92",
        "RELEASE_NOTES_v1.3.92.md",
        ["1.3.92-industrial"],
    ),
    (
        "1.3.92",
        "native/abs_native/src/p2p_transport.rs",
        ["read_message", "v1.3.92"],
    ),
    (
        "1.3.92",
        "network/p2p_node.py",
        ["_native_read_message", "read_message"],
    ),
    (
        "1.3.92",
        "observability/metrics.py",
        ["abs_p2p_native_read_message"],
    ),
    (
        "1.3.93",
        "RELEASE_NOTES_v1.3.93.md",
        ["1.3.93-industrial"],
    ),
    (
        "1.3.93",
        "native/abs_native/src/p2p_transport.rs",
        ["write_message", "v1.3.93"],
    ),
    (
        "1.3.93",
        "network/p2p_node.py",
        ["_native_write_message", "_write_message"],
    ),
    (
        "1.3.93",
        "observability/metrics.py",
        ["abs_p2p_native_write_message"],
    ),
    (
        "1.3.94",
        "runtime/config.py",
        ["1.3.94-industrial"],
    ),
    (
        "1.3.94",
        "native/abs_native/src/p2p_transport.rs",
        ["read_messages", "v1.3.94"],
    ),
    (
        "1.3.94",
        "network/p2p_node.py",
        ["_native_read_messages", "_pending_msgs"],
    ),
    (
        "1.3.94",
        "observability/metrics.py",
        ["abs_p2p_native_read_messages"],
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
        if not ver.startswith("1.3.94"):
            errors.append(f"node_version expected 1.3.94-*, got {ver}")
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
