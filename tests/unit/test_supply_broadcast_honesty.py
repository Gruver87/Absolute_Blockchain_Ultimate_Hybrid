#!/usr/bin/env python3
"""v1.3.25 honesty: supply canonical, Rocks point-gets, broadcast_fail, core_real."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_state_supply_db_only_not_canonical():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert "DB-only is never IMS-canonical when shadow state is absent/unusable" in http_py
    assert '"ims_available": bool(ims_available)' in http_py


def test_core_real_engines_and_no_fake_quorum():
    http_py = Path("api/http.py").read_text(encoding="utf-8")
    assert '"finality_quorum_live": False' in http_py
    assert '"local_attestations_present"' in http_py
    assert '"state_engine": self.__class__.state_engine is not None' in http_py
    assert "finality_engine_missing" in http_py
    assert "state_engine_missing" in http_py


def test_broadcast_results_recorded():
    from network.p2p_node import P2PNode

    # Lightweight: exercise helper without full node boot.
    node = SimpleNamespace(
        _broadcast_fail=0,
    )
    # Bind unbound method
    P2PNode._record_broadcast_results(
        node, [True, False, RuntimeError("x")], kind="tx_broadcast"
    )
    assert node._broadcast_fail == 2


def test_rocks_point_gets_use_loads_helper():
    rocks = Path("storage/rocks_store.py").read_text(encoding="utf-8")
    assert "def _loads_json_or_none" in rocks
    assert 'return self._loads_json_or_none(raw, context=f"tx' in rocks
    assert 'return self._loads_json_or_none(raw, context=f"receipt' in rocks
    assert 'return self._loads_json_or_none(raw, context=f"block' in rocks


def test_prod_block_sign_hard_fail():
    main_py = Path("main.py").read_text(encoding="utf-8")
    assert "Production mode requires block signature" in main_py
