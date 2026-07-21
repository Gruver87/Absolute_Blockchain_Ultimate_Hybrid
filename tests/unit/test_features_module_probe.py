"""Feature module import probes and /features module_probes."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from features import OPTIONAL_MODULE_PROBES, probe_optional_module


def test_probe_wasm_importable():
    probe = probe_optional_module(*OPTIONAL_MODULE_PROBES["wasm"])
    assert probe["module_importable"] is True
    assert probe["import_error"] is None


def test_probe_plasma_importable():
    probe = probe_optional_module(*OPTIONAL_MODULE_PROBES["plasma"])
    assert probe["module_importable"] is True


def test_probe_unknown_module_fail_loud():
    probe = probe_optional_module("features.no_such_module_xyz", "NoClass")
    assert probe["module_importable"] is False
    assert probe["import_error"]
