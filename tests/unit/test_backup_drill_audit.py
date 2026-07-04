#!/usr/bin/env python3
"""Backup DB drill and external audit automation tests."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.external_audit import evaluate_automated, sync_automated_items


def test_evaluate_automated_dr_drill_passes():
    results = evaluate_automated()
    ok, note = results["Disaster recovery drill for multi-node devnet completed"]
    assert ok, note


def test_sync_automated_marks_dr_drill(tmp_path):
    status = tmp_path / "audit.json"
    marked = sync_automated_items(status_path=status)
    assert "Disaster recovery drill for multi-node devnet completed" in marked
