"""Wave 44 — unified L2 status API and MEV SQLite persistence."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_mev_analysis_persists():
    from features.mev_analyzer import MEVAnalyzer, Transaction
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "m.db"))
    db.initialize()

    m1 = MEVAnalyzer(db=db)
    txs = [
        Transaction("0xabc", "0xu1", "0xpool", 10, 100, 1),
        Transaction("0xdef", "0xu2", "0xpool", 5, 50, 2),
    ]
    r = m1.detect_sandwich_opportunity(txs)
    assert r["opportunity"] is True

    m2 = MEVAnalyzer(db=db)
    assert m2.get_statistics()["total_attacks"] >= 1
    assert m2.get_statistics()["persisted"] is True


def test_mev_frontrun_recorded():
    from features.mev_analyzer import MEVAnalyzer, Transaction
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "f.db"))
    db.initialize()
    mev = MEVAnalyzer(db=db)
    tx = Transaction("0x111", "0xa", "0xb", 20.0, 50, 3)
    out = mev.simulate_frontrun(tx, bot_balance=1000.0)
    assert out["opportunity"] is True
    assert out["executed"] is False
    assert "estimated_profit" in out
    assert mev.get_statistics()["attack_types"]["frontrun"] >= 1


def test_mev_simulator_name_is_compatibility_alias():
    from features.mev_analyzer import MEVAnalyzer
    from features.mev_simulator import MEVSimulator

    assert MEVSimulator is MEVAnalyzer


def test_l2_status_aggregator():
    from api.http import _build_l2_status
    from features.lightning import LightningNetwork
    from features.plasma import PlasmaChain
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "l2.db"))
    db.initialize()

    class _H:
        lightning = LightningNetwork("0x" + "1" * 40, db=db)
        plasma = PlasmaChain(db=db)
        crypto_will = None
        wasm_vm = None
        ai_manager = None

    st = _build_l2_status(_H)
    assert "lightning" in st["modules"]
    assert "plasma" in st["modules"]
    assert st["l2_persisted"] is True
