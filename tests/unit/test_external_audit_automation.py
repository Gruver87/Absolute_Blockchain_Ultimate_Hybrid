#!/usr/bin/env python3
"""Extended external audit automation tests."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.external_audit import evaluate_automated


def test_automated_runbook_passes():
    ok, note = evaluate_automated()["Incident response runbook documented"]
    assert ok, note


def test_automated_bridge_l1_passes():
    ok, note = evaluate_automated()["Bridge L1 RPC keys rotated from dev placeholders"]
    assert ok, note


def test_automated_validator_manifest_passes():
    ok, note = evaluate_automated()[
        "Production validator manifest published (no runtime key derivation)"
    ]
    assert ok, note
