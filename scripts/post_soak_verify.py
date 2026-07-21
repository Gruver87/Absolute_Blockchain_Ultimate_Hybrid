#!/usr/bin/env python3
"""Post-soak verification — everything shipped after the 48h soak.

Covers the Rust/P2P/consensus/state/native-hash/Rocks CF wave:
  1) abs_native kernel surface smoke
  2) targeted unit tests
  3) industrial_gate.py
  4) k8s_prod_gate.py

Usage (repo root):
  python scripts/post_soak_verify.py
  python scripts/post_soak_verify.py --rebuild-native
  python scripts/post_soak_verify.py --with-clippy
  .\\scripts\\post_soak_verify.ps1
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Unit tests for work done after soak (P2P wire → consensus → amount → Rocks CF → features).
POST_SOAK_TESTS = [
    "tests/unit/test_native_p2p_wire.py",
    "tests/unit/test_native_peer_validation.py",
    "tests/unit/test_native_consensus_select.py",
    "tests/unit/test_native_amount_state.py",
    "tests/unit/test_native_consensus_hash.py",
    "tests/unit/test_native_crypto.py",
    "tests/unit/test_native_batch_hash.py",
    "tests/unit/test_distributed_sharding.py",
    "tests/unit/test_cross_shard_gossip.py",
    "tests/unit/test_zk_proofs.py",
    "tests/unit/test_multisig_wallet.py",
    "tests/unit/test_smart_accounts_auth.py",
    "tests/unit/test_postquantum_fail_closed.py",
    "tests/unit/test_rocks_store.py",
    "tests/unit/test_p2p_industrial.py",
    "tests/unit/test_p2p_ops_errors.py",
    "tests/unit/test_status_honesty.py",
    "tests/unit/test_silent_except_honesty.py",
    "tests/unit/test_cors_receipt_ready_honesty.py",
    "tests/unit/test_sync_mesh_bridge_honesty.py",
    "tests/unit/test_mesh_mining_ready.py",
    "tests/unit/test_rocks_topology_honesty.py",
    "tests/unit/test_bind_ready_status_honesty.py",
    "tests/unit/test_core_engines_honesty.py",
    "tests/unit/test_supply_broadcast_honesty.py",
    "tests/unit/test_gather_mutate_honesty.py",
    "tests/unit/test_decode_catchup_honesty.py",
    "tests/unit/test_ws_status_clone_honesty.py",
    "tests/unit/test_v1329_honesty.py",
    "tests/unit/test_v1330_honesty.py",
    "tests/unit/test_v1331_honesty.py",
    "tests/unit/test_v1332_honesty.py",
    "tests/unit/test_v1333_honesty.py",
    "tests/unit/test_sqlite_reorg_parity.py",
    "tests/unit/test_bridge_health.py",
    "tests/unit/test_rpc_methods.py",
]

REQUIRED_NATIVE_SYMBOLS = [
    "parse_p2p_wire_line",
    "encode_p2p_wire_message",
    "validate_p2p_status_payload",
    "validate_p2p_attestation_payload",
    "validate_p2p_block_announce",
    "validate_p2p_state_root_request",
    "validate_p2p_state_root_response",
    "validate_p2p_handshake_payload",
    "validate_p2p_get_blocks_payload",
    "validate_p2p_wire_tx",
    "validate_p2p_mempool_batch",
    "validate_p2p_validator_register",
    "validate_p2p_peers_list",
    "validate_p2p_get_block",
    "validate_p2p_get_block_by_hash",
    "validate_p2p_blocks_batch",
    "validate_p2p_cross_shard_tx",
    "validate_p2p_cross_shard_ack",
    "validate_p2p_shard_migration",
    "consensus_stake_weighted_proposer",
    "consensus_fisher_yates_committee",
    "amount_to_satoshi",
    "state_engine_apply_transactions",
    "plan_transfer_fees",
    "can_afford_transfer",
    "RocksEngine",
]


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> int:
    print(f"\n>>> {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(cwd or ROOT), env=env)
    return int(proc.returncode)


def step_rebuild_native() -> int:
    print("\n=== [1/5] Rebuild abs_native wheel ===")
    crate = ROOT / "native" / "abs_native"
    out = ROOT / "dist" / "native_wheel"
    out.mkdir(parents=True, exist_ok=True)
    rc = _run(
        ["maturin", "build", "--release", "-o", str(out)],
        cwd=crate,
    )
    if rc != 0:
        return rc
    wheels = sorted(out.glob("abs_native-*.whl"))
    if not wheels:
        print("FAIL: no abs_native wheel produced")
        return 1
    wheel = wheels[-1]
    return _run(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", str(wheel)]
    )


def step_native_smoke() -> tuple[int, dict]:
    print("\n=== [2/5] Native kernel smoke ===")
    report: dict = {"available": False, "missing": [], "rocks_cf": False, "errors": []}
    try:
        import abs_native  # type: ignore
    except Exception as exc:
        report["errors"].append(f"import abs_native failed: {exc}")
        print(f"FAIL: {report['errors'][-1]}")
        return 1, report

    report["available"] = True
    missing = [name for name in REQUIRED_NATIVE_SYMBOLS if not hasattr(abs_native, name)]
    report["missing"] = missing
    if missing:
        print("FAIL: missing exports:")
        for name in missing:
            print(f"  - {name}")
        return 1, report

    # P2P + amount + consensus quick vectors
    from crypto import native

    hs = native.validate_p2p_handshake_payload(
        {
            "chain_id": 1,
            "height": 10,
            "head_hash": "ab" * 32,
            "node_id": "abs-18080",
            "p2p_port": 18080,
            "version": "1.0",
        }
    )
    if not hs or hs.get("accepted") is not True:
        report["errors"].append("handshake validator failed")
        print("FAIL: handshake validator")
        return 1, report

    peers = native.validate_p2p_peers_list(["127.0.0.1:18080"])
    if peers != ["127.0.0.1:18080"]:
        report["errors"].append("peers_list validator failed")
        print("FAIL: peers_list validator")
        return 1, report

    tx = native.validate_p2p_cross_shard_tx(
        {
            "tx_id": "abcd1234efgh5678",
            "from_shard": 0,
            "to_shard": 1,
            "from_addr": "0x" + "a" * 40,
            "to_addr": "0x" + "b" * 40,
            "amount": 1.0,
        }
    )
    if not tx:
        report["errors"].append("cross_shard_tx validator failed")
        print("FAIL: cross_shard_tx validator")
        return 1, report

    if native.amount_to_satoshi(1) != 1_000_000:
        report["errors"].append("amount_to_satoshi parity failed")
        print("FAIL: amount_to_satoshi")
        return 1, report

    # Rocks CF kwarg present on current wheel
    import inspect

    sig = inspect.signature(abs_native.RocksEngine)
    report["rocks_cf"] = "column_families" in sig.parameters
    if not report["rocks_cf"]:
        report["errors"].append("RocksEngine missing column_families kwarg (rebuild wheel)")
        print("FAIL: RocksEngine.column_families missing — run with --rebuild-native")
        return 1, report

    print("OK: native kernels + P2P/amount/CF surface")
    return 0, report


def step_pytest() -> int:
    print("\n=== [3/5] Targeted post-soak pytest ===")
    tests = [str(ROOT / t) for t in POST_SOAK_TESTS if (ROOT / t).is_file()]
    if not tests:
        print("FAIL: no test files found")
        return 1
    env = os.environ.copy()
    env.setdefault("ABS_REQUIRE_NATIVE_CRYPTO", "true")
    return _run(
        [sys.executable, "-m", "pytest", *tests, "-q", "--tb=line"],
        env=env,
    )


def step_industrial_gate() -> int:
    print("\n=== [4/5] Industrial gate ===")
    return _run([sys.executable, str(ROOT / "scripts" / "industrial_gate.py")])


def step_k8s_prod_gate() -> int:
    print("\n=== [5/5] K8s prod gate ===")
    return _run([sys.executable, str(ROOT / "scripts" / "k8s_prod_gate.py")])


def step_clippy() -> int:
    print("\n=== [extra] cargo clippy -D warnings ===")
    rc1 = _run(
        [
            "cargo",
            "clippy",
            "--manifest-path",
            str(ROOT / "native" / "abs_native" / "Cargo.toml"),
            "--all-targets",
            "--",
            "-D",
            "warnings",
        ]
    )
    if rc1 != 0:
        return rc1
    return _run(
        [
            "cargo",
            "clippy",
            "--manifest-path",
            str(ROOT / "bridge" / "rust_bridge" / "Cargo.toml"),
            "--all-targets",
            "--",
            "-D",
            "warnings",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Post-soak Absolute verify (single entry)")
    parser.add_argument(
        "--rebuild-native",
        action="store_true",
        help="maturin build + pip install abs_native before tests",
    )
    parser.add_argument(
        "--with-clippy",
        action="store_true",
        help="also run cargo clippy -D warnings on abs_native + rust_bridge",
    )
    parser.add_argument(
        "--json-out",
        default="",
        help="optional path for JSON summary (default: data/post_soak_verify.json)",
    )
    args = parser.parse_args()

    started = time.time()
    results: dict = {"ok": False, "steps": {}, "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    print("Absolute Blockchain — post-soak verification")
    print(f"ROOT={ROOT}")

    if args.rebuild_native:
        rc = step_rebuild_native()
        results["steps"]["rebuild_native"] = rc
        if rc != 0:
            return _finish(results, started, args.json_out)

    rc, smoke = step_native_smoke()
    results["steps"]["native_smoke"] = rc
    results["native_smoke"] = smoke
    if rc != 0:
        return _finish(results, started, args.json_out)

    rc = step_pytest()
    results["steps"]["pytest"] = rc
    if rc != 0:
        return _finish(results, started, args.json_out)

    rc = step_industrial_gate()
    results["steps"]["industrial_gate"] = rc
    if rc != 0:
        return _finish(results, started, args.json_out)

    rc = step_k8s_prod_gate()
    results["steps"]["k8s_prod_gate"] = rc
    if rc != 0:
        return _finish(results, started, args.json_out)

    if args.with_clippy:
        rc = step_clippy()
        results["steps"]["clippy"] = rc
        if rc != 0:
            return _finish(results, started, args.json_out)

    results["ok"] = True
    return _finish(results, started, args.json_out)


def _finish(results: dict, started: float, json_out: str) -> int:
    results["elapsed_sec"] = round(time.time() - started, 2)
    results["ok"] = bool(results.get("ok")) and all(
        int(v) == 0 for v in results.get("steps", {}).values()
    )
    out = Path(json_out) if json_out else ROOT / "data" / "post_soak_verify.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    if results["ok"]:
        print(f"PASS: post-soak verify ({results['elapsed_sec']}s)")
        print(f"Report: {out}")
        return 0
    print(f"FAIL: post-soak verify ({results['elapsed_sec']}s)")
    print("Steps:", results.get("steps"))
    print(f"Report: {out}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
