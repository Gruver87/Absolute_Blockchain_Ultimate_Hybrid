#!/usr/bin/env python3
"""Pre-mainnet audit runner smoke tests."""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def _load_audit():
    path = os.path.join(ROOT, "scripts", "pre_mainnet_audit.py")
    spec = importlib.util.spec_from_file_location("pre_mainnet_audit", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_pre_mainnet_audit_passes_locally():
    audit = _load_audit()
    errors, warnings, checklist = audit.run_checks()
    assert isinstance(errors, list)
    assert isinstance(warnings, list)
    assert len(checklist) >= 5
    assert errors == [], errors


def test_pre_mainnet_report_written():
    audit = _load_audit()
    errors, warnings, checklist = audit.run_checks()
    path = audit.write_report(errors, warnings, checklist)
    assert path.is_file()
    assert path.name == "pre_mainnet_audit.json"
