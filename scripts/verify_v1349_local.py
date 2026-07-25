#!/usr/bin/env python3
"""Local smoke for Absolute Hybrid v1.3.45–v1.3.49 (native EVM CALL wave).

Run from repo root (PowerShell / bash):

  python scripts/verify_v1349_local.py

Optional:
  python scripts/verify_v1349_local.py --rebuild-native
  python scripts/verify_v1349_local.py --strict   # fail if abs_native missing

Exit 0 = all checks passed. Prints a short PASS/FAIL report.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TESTS = [
    "tests/unit/test_v1345_native_apply_honesty.py",
    "tests/unit/test_v1346_mixed_apply.py",
    "tests/unit/test_v1347_nested_call_effects.py",
    "tests/unit/test_v1348_nested_call_gas.py",
    "tests/unit/test_v1349_nested_call_decode.py",
    "tests/unit/test_evm_host_bridge.py",
    "tests/unit/test_evm_call.py",
    "tests/unit/test_evm_native_host_ops.py",
]

KERNELS = [
    "evm_plan_nested_call_effects",
    "evm_plan_nested_call_gas",
    "evm_decode_nested_call_frame",
    "blockchain_apply_host_effects",
]


def _ok(msg: str) -> None:
    print(f"  PASS  {msg}")


def _fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def step_rebuild_native() -> int:
    print("\n== rebuild abs_native ==")
    env = os.environ.copy()
    if os.name == "nt" and Path("D:/").exists():
        env["CARGO_TARGET_DIR"] = r"D:\cargo-target\abs_native"
    out = ROOT / "native" / "abs_native" / "target" / "wheels"
    out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "maturin",
        "build",
        "--release",
        "-m",
        "native/abs_native/Cargo.toml",
        "--out",
        str(out),
    ]
    print(">>>", " ".join(cmd))
    rc = subprocess.call(cmd, cwd=str(ROOT), env=env)
    if rc != 0:
        return rc
    wheels = sorted(out.glob("abs_native-*.whl"))
    if not wheels:
        _fail("no wheel produced")
        return 1
    wheel = wheels[-1]
    print(">>> pip install", wheel.name)
    return subprocess.call(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", str(wheel)],
        cwd=str(ROOT),
    )


def step_env_and_kernels(*, strict: bool) -> list[str]:
    print("\n== env / kernels ==")
    errors: list[str] = []
    from runtime.config import Config

    ver = Config().node_version
    if not str(ver).startswith("1.3.49"):
        errors.append(f"node_version expected 1.3.49-*, got {ver!r}")
        _fail(f"node_version={ver}")
    else:
        _ok(f"node_version={ver}")

    try:
        import abs_native as an  # type: ignore

        _ok(f"abs_native import ok ({getattr(an, '__file__', '?')})")
        for name in KERNELS:
            if hasattr(an, name):
                _ok(f"abs_native.{name}")
            else:
                errors.append(f"missing abs_native.{name}")
                _fail(f"abs_native.{name}")
    except Exception as exc:
        msg = f"abs_native not importable: {exc}"
        if strict:
            errors.append(msg)
            _fail(msg)
        else:
            print(f"  WARN  {msg} (Python fallback will be used; pass --strict to fail)")

    return errors


def step_functional() -> list[str]:
    print("\n== functional smoke ==")
    errors: list[str] = []
    from crypto import native

    # Decode CALL frame (Absolute: top = gas)
    stack = ["32", "64", "4", "32", "7", "2748", "100000"]  # ret..gas
    frame = native.evm_decode_nested_call_frame(0xF1, stack)
    checks = [
        (frame.get("kind") == "call", f"decode kind={frame.get('kind')}"),
        (int(frame["gas"]) == 100_000, f"decode gas={frame.get('gas')}"),
        (int(frame["to_word"]) == 0xABC, f"decode to={frame.get('to_word')}"),
        (int(frame["value"]) == 7, f"decode value={frame.get('value')}"),
        (int(frame["stack_consumed"]) == 7, f"decode consumed={frame.get('stack_consumed')}"),
    ]
    for ok, label in checks:
        if ok:
            _ok(label)
        else:
            errors.append(label)
            _fail(label)

    mem = b"\x00" * 32 + b"abcd"
    framed = native.evm_decode_nested_call_frame(0xF1, stack, mem)
    if framed.get("call_data_hex") == "61626364":
        _ok("decode call_data_hex")
    else:
        errors.append(f"call_data_hex={framed.get('call_data_hex')}")
        _fail("decode call_data_hex")

    gas = native.evm_plan_nested_call_gas(64_000, 0, 1, "call")
    if gas.get("stipend_applied") is True and int(gas["call_gas"]) == min(64_000, 63_000 + 2300):
        _ok(f"gas planner call_gas={gas['call_gas']} native={gas.get('native_plan')}")
    else:
        errors.append(f"gas planner bad: {gas}")
        _fail("gas planner")

    effects = native.evm_plan_nested_call_effects(
        kind="staticcall",
        parent_read_only=False,
        caller="0x" + "11" * 20,
        target="0x" + "22" * 20,
        value_wei=0,
        success=True,
    )
    if isinstance(effects, dict) and effects:
        _ok(f"effects planner ok native={effects.get('native_plan')}")
    else:
        errors.append(f"effects planner bad: {effects}")
        _fail("effects planner")

    # Wiring needles
    bridge = (ROOT / "execution" / "evm_host_bridge.py").read_text(encoding="utf-8")
    if "evm_decode_nested_call_frame" in bridge:
        _ok("bridge wires decode")
    else:
        errors.append("evm_host_bridge missing decode wire")
        _fail("bridge wires decode")

    lib = (ROOT / "native" / "abs_native" / "src" / "lib.rs").read_text(encoding="utf-8")
    if "fn evm_decode_nested_call_frame" in lib:
        _ok("lib.rs defines decode")
    else:
        errors.append("lib.rs missing decode fn")
        _fail("lib.rs defines decode")

    return errors


def step_pytest() -> int:
    print("\n== pytest (CALL wave) ==")
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=line", *TESTS]
    print(">>>", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def step_industrial_needles() -> list[str]:
    print("\n== industrial gate needles (v1.3.49) ==")
    errors: list[str] = []
    native_py = (ROOT / "crypto" / "native.py").read_text(encoding="utf-8")
    bridge_py = (ROOT / "execution" / "evm_host_bridge.py").read_text(encoding="utf-8")
    lib = (ROOT / "native" / "abs_native" / "src" / "lib.rs").read_text(encoding="utf-8")
    for label, ok in [
        ("crypto/native.py export", "def evm_decode_nested_call_frame" in native_py),
        ("bridge wire", "evm_decode_nested_call_frame" in bridge_py),
        ("lib.rs fn", "fn evm_decode_nested_call_frame" in lib),
    ]:
        if ok:
            _ok(label)
        else:
            errors.append(label)
            _fail(label)
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Local verify for Absolute Hybrid v1.3.49 CALL wave")
    ap.add_argument("--rebuild-native", action="store_true", help="maturin build + pip install wheel")
    ap.add_argument("--strict", action="store_true", help="fail if abs_native missing")
    ap.add_argument("--skip-pytest", action="store_true", help="only smoke, no pytest")
    args = ap.parse_args()

    print("Absolute Hybrid — local verify (v1.3.45–1.3.49 CALL wave)")
    print(f"ROOT={ROOT}")
    print(f"Python={sys.executable} ({sys.version.split()[0]})")

    if args.rebuild_native:
        rc = step_rebuild_native()
        if rc != 0:
            print("\nRESULT: FAIL (rebuild)")
            return rc

    errors: list[str] = []
    errors.extend(step_env_and_kernels(strict=args.strict))
    errors.extend(step_functional())
    errors.extend(step_industrial_needles())

    pytest_rc = 0
    if not args.skip_pytest:
        pytest_rc = step_pytest()
        if pytest_rc != 0:
            errors.append(f"pytest exit={pytest_rc}")

    print("\n" + "=" * 60)
    if errors:
        print(f"RESULT: FAIL ({len(errors)} issue(s))")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("RESULT: PASS — native CALL wave looks healthy on this machine")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
