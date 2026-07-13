#!/usr/bin/env python3
"""Bridge L1 cutover evidence suite tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_bridge_cutover_evidence_scripts_exist():
    assert (ROOT / "scripts" / "bridge_cutover_evidence_suite.ps1").is_file()
    assert (ROOT / "scripts" / "prepare_bridge_l1_cutover.ps1").is_file()
    assert (ROOT / ".env.bridge.cutover.example").is_file()


def test_testnet_vps_ops_scripts_exist():
    assert (ROOT / "scripts" / "testnet_backup_restore.ps1").is_file()
    assert (ROOT / "scripts" / "testnet_log_rotate.sh").is_file()
    assert (ROOT / "scripts" / "restore_chainstore.py").is_file()
