#!/usr/bin/env python3
"""Fail-loud honesty for prod-critical silent-except surfaces."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from blockchain.immutable_state import ImmutableStateManager
from sync.sync_engine import SyncEngine


def test_sync_state_logs_wire_probe_failure(capsys):
    node = SimpleNamespace(
        blockchain=SimpleNamespace(
            get_state_root=lambda: "abc",
            get_height=lambda: 1,
            get_block=lambda _h: None,
        ),
        request_peer_state_roots_sync=MagicMock(side_effect=RuntimeError("boom")),
        p2p=SimpleNamespace(_state_consistent=True),
    )
    # SyncEngine expects node with peers collector
    eng = SyncEngine(node)
    eng._collect_p2p_peers = lambda: []  # type: ignore
    ok = eng.sync_state()
    captured = capsys.readouterr()
    assert "wire probe failed" in captured.out
    assert eng.get_status().get("wire_probe_ok") is False
    assert eng.get_status().get("wire_probe_probed") is True
    assert ok is True  # no peers/mismatches — consistent but probe failed


def test_sync_status_unknown_probe_is_fail_closed():
    eng = SyncEngine(SimpleNamespace(p2p=SimpleNamespace(_state_consistent=True)))
    eng._collect_p2p_peers = lambda: []  # type: ignore
    st = eng.get_status()
    assert st.get("wire_probe_ok") is False
    assert st.get("wire_probe_probed") is False


def test_ims_reconcile_fail_loud_nonce():
    store = SimpleNamespace(
        get_balance_satoshi=lambda _a: 1_000_000,
        get_nonce=MagicMock(side_effect=RuntimeError("nonce down")),
    )
    ims = ImmutableStateManager()
    raised = False
    try:
        ims.reconcile_from_store(store, ["alice"], fail_loud=True)
    except RuntimeError:
        raised = True
    assert raised


def test_ims_reconcile_nonce_soft_without_fail_loud(capsys):
    store = SimpleNamespace(
        get_balance_satoshi=lambda _a: 2_000_000,
        get_nonce=MagicMock(side_effect=RuntimeError("nonce down")),
    )
    ims = ImmutableStateManager()
    n = ims.reconcile_from_store(store, ["bob"], fail_loud=False)
    assert n == 1
    assert ims.get_balance_satoshi("bob") == 2_000_000
    assert "get_nonce failed" in capsys.readouterr().out


def test_state_root_status_peer_probe_error_surface():
    # Static contract: api/http.py must expose peer_probe_error key
    from pathlib import Path

    text = Path("api/http.py").read_text(encoding="utf-8")
    assert "peer_probe_error" in text
    assert "record_state_root_mismatch failed" in Path("core/blockchain.py").read_text(
        encoding="utf-8"
    )
    assert "genesis meta write failed" in Path("core/blockchain.py").read_text(encoding="utf-8")
    assert "sync_state probe failed" in Path("main.py").read_text(encoding="utf-8")
