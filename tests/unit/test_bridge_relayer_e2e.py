"""Wave 59 — bridge relayer L1 queue e2e (incoming + outbound)."""
import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from runtime.config import Config
from storage.database import Database
from bridge.abs_bridge import RustBridge
from bridge.l1_rpc import load_l1_queue


@pytest.fixture
def bridge_env(tmp_path):
    path = str(tmp_path / "bridge.db")
    cfg = Config()
    cfg.db_path = path
    cfg.bridge_mode = "simulator"
    cfg.bridge_auto_confirm_sec = 0
    cfg.bridge_l1_queue_path = str(tmp_path / "l1_queue.json")
    cfg.burn_address = "0x" + "d" * 40
    db = Database(path)
    db.initialize()
    db.set_balance("0xalice", 100.0)
    br = RustBridge(cfg, db, None)
    yield br, db, cfg, tmp_path
    db.close()


def test_outbound_l1_queue_on_lock(bridge_env):
    br, db, cfg, tmp_path = bridge_env
    res = br.lock_and_bridge(
        "0xalice", "ethereum", "0xrecipient", 10.0, l1_tx_hash="0x" + "aa" * 32
    )
    assert res.get("l1_queued") is True
    q = load_l1_queue(cfg.bridge_l1_queue_path)
    assert len(q.get("outbound", [])) == 1
    assert q["outbound"][0]["l1_tx_hash"] == "0x" + "aa" * 32


def test_incoming_l1_queue_on_register(bridge_env):
    br, db, cfg, tmp_path = bridge_env
    br.enqueue_l1_incoming(
        "0x" + "bb" * 32,
        "0xrecipient",
        25.0,
        "ethereum",
        tx_id="ext-tx-1",
    )
    q = load_l1_queue(cfg.bridge_l1_queue_path)
    assert len(q.get("incoming", [])) == 1
    row = q["incoming"][0]
    assert row["recipient"] == "0xrecipient"
    assert float(row["amount"]) == 25.0


def test_confirm_incoming_enqueues_l1_hash(bridge_env):
    br, db, cfg, tmp_path = bridge_env
    l1 = "0x" + "cc" * 32
    br.confirm_incoming("ext-1", "0xrecipient", 15.0, "ethereum", l1_tx_hash=l1)
    q = load_l1_queue(cfg.bridge_l1_queue_path)
    assert any(e.get("l1_tx_hash") == l1 for e in q.get("incoming", []))


def test_relayer_processes_mock_l1_incoming(monkeypatch, bridge_env):
    import importlib.util

    br, db, cfg, tmp_path = bridge_env
    secret = "test-bridge-secret"
    cfg.bridge_oracle_secret = secret
    os.environ["BRIDGE_ORACLE_SECRET"] = secret

    l1 = "0x" + "dd" * 32
    br.enqueue_l1_incoming(l1, "0xrecipient", 5.0, "ethereum", tx_id="in-1")

    path = os.path.join(ROOT, "scripts", "bridge_relayer.py")
    spec = importlib.util.spec_from_file_location("bridge_relayer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from bridge import relayer as relayer_core

    monkeypatch.setattr(relayer_core, "is_tx_confirmed", lambda *a, **k: True)
    calls = []

    def fake_post(base, pth, payload, sec):
        calls.append((pth, payload))
        if pth.endswith("/incoming"):
            return br.confirm_incoming(
                payload["tx_id"],
                payload["recipient"],
                float(payload["amount"]),
                payload["from_chain"],
                l1_tx_hash=payload.get("tx_hash", ""),
            )
        return {"confirmed": True}

    monkeypatch.setattr(relayer_core, "oracle_post", fake_post)
    n = mod.process_l1_queue("http://127.0.0.1:8080", secret, cfg.bridge_l1_queue_path)
    assert n == 1
    assert db.get_balance("0xrecipient") == 5.0
    assert any(c[0].endswith("/incoming") for c in calls)
