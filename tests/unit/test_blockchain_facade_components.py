# tests/unit/test_blockchain_facade_components.py
"""Blockchain facade delegates to core.components (TxPipeline / StateService / ZK)."""

from __future__ import annotations

import inspect
from pathlib import Path

from core.blockchain import Blockchain
from core.components import NullZkGateway, StateService, TxPipeline
from core.components.zk_gateway import build_zk_gateway


def test_blockchain_wires_components(tmp_path, monkeypatch):
    from runtime.config import Config
    from storage.database import Database
    from storage.factory import open_storage

    monkeypatch.setenv("ABS_NATIVE_MODE", "auto")
    cfg = Config()
    cfg.data_dir = str(tmp_path)
    db = Database(str(tmp_path / "t.db"))
    storage = open_storage(db, repair_on_open=False)
    bc = Blockchain(cfg, db=db, storage=storage)
    assert isinstance(bc.tx_pipeline, TxPipeline)
    assert isinstance(bc.state_service, StateService)
    assert isinstance(bc.zk_gateway, NullZkGateway)


def test_validate_transaction_is_thin_delegate():
    src = inspect.getsource(Blockchain.validate_transaction)
    assert "tx_pipeline" in src
    assert "insufficient_funds" not in src
    assert "plan_transfer_fees" not in src


def test_apply_transaction_is_thin_delegate():
    src = inspect.getsource(Blockchain._apply_transaction)
    assert "state_service" in src
    assert "balance_delta" not in src


def test_blockchain_py_has_no_validate_body_needle():
    text = Path("core/blockchain.py").read_text(encoding="utf-8")
    # Body of validation lived here; must not reappear as full implementation.
    assert "error\": \"gas_too_low\"" not in text
    assert "nonce_mismatch (got" not in text


def test_null_zk_rejects():
    g = build_zk_gateway(None, enabled=False)
    assert g.enabled() is False
    r = g.validate_zk_tx(object())
    assert r.valid is False
