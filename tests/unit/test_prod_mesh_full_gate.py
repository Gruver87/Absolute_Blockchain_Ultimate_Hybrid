#!/usr/bin/env python3
"""ProdMeshFull gate wiring smoke tests."""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def test_test_blockchain_full_exposes_prod_mesh_full_flag():
    body = _read("scripts/test_blockchain_full.ps1")
    assert "ProdMeshFull" in body
    assert "prod_evidence_suite.ps1" in body


def test_prod_mesh_full_wrapper_delegates():
    body = _read("scripts/prod_mesh_full.ps1")
    assert "-ProdMeshFull" in body
    assert "test_blockchain_full.ps1" in body


def test_prod_evidence_suite_accepts_failover_wait():
    body = _read("scripts/prod_evidence_suite.ps1")
    assert "FailoverWaitSec" in body
    assert re.search(r"prod_mesh_failover\.ps1.*WaitSec", body)
