#!/usr/bin/env python3
"""v1.3.36 honesty: WASM/finality/reorg/RANDAO/chain_storage."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_wasm_honesty_and_binary_gate():
    text = Path("features/wasm_vm.py").read_text(encoding="utf-8")
    assert "wasmtime_available" in text
    assert "pseudo_token_host" in text
    assert "Binary WASM requires wasmtime" in text
    http = Path("api/http.py").read_text(encoding="utf-8")
    assert "wasm_operational" in http


def test_finality_standalone_observer():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "standalone observer" in main
    assert "consensus_bound=false" in main
    http = Path("api/http.py").read_text(encoding="utf-8")
    assert "finality_engine_standalone_observer" in http
    assert "standalone_observer" in http


def test_reorg_no_finalized_heuristic():
    text = Path("features/reorg_predictor.py").read_text(encoding="utf-8")
    assert "heuristic_low_risk" in text
    assert 'return "finalized"' not in text
    assert "not_consensus_finality" in text


def test_validator_selection_not_randao():
    main = Path("main.py").read_text(encoding="utf-8")
    assert "deterministic_hash_selection" in main
    assert "randao_commit_reveal=false" in main
    cfg = Path("runtime/config.py").read_text(encoding="utf-8")
    assert "FEATURE_VALIDATOR_SELECTION" in cfg
    vs = Path("consensus/validator_selection.py").read_text(encoding="utf-8")
    assert "randao_commit_reveal" in vs
    assert "proposer_unbiasable" in vs


def test_chain_storage_atomic_replace():
    text = Path("storage/chain_storage.py").read_text(encoding="utf-8")
    assert "abs_chain_replace_" in text
    assert "os.rename(tmp_blocks" in text
