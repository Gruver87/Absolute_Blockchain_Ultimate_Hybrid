#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/native/abs_native"

python -m pip install --upgrade maturin
python -m maturin build --release --out target/wheels
python -m pip install --force-reinstall target/wheels/*.whl
python -c "import abs_native; print('abs_native OK:', abs_native.sha256_hex(b'absolute')[:16]); assert hasattr(abs_native, 'evm_run_until_halt')"
