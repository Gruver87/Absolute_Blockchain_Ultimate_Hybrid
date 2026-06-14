"""Wave 45 — reorg predictor persistence, fixed /reorg/* API, /features enrichment."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_reorg_depth_persists():
    from features.reorg_predictor import ReorgPredictor
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "r.db"))
    db.initialize()

    rp = ReorgPredictor(db=db)
    depth = rp.predict_reorg_depth(100.0, 10.0)
    assert depth >= 3

    rp2 = ReorgPredictor(db=db)
    assert rp2.get_stats()["persisted"] is True
    assert rp2.get_stats()["assessments"] >= 1
    hist = rp2.get_history(10)
    assert any(h.get("kind") == "depth" for h in hist)


def test_reorg_fork_analysis():
    from features.reorg_predictor import ReorgPredictor

    rp = ReorgPredictor()
    main = [{"hash": "a", "number": 0}, {"hash": "b", "number": 1}]
    fork = [{"hash": "a", "number": 0}, {"hash": "c", "number": 1}]
    out = rp.analyze_fork(main, fork)
    assert out["fork_detected"] is True
    assert out["fork_depth"] == 1


def test_reorg_live_peers():
    from features.reorg_predictor import ReorgPredictor

    rp = ReorgPredictor()
    out = rp.analyze_live_peers(100, [98, 99, 101])
    assert out["max_peer_gap"] == 2
    assert "risk" in out


def test_db_reorg_assessments_roundtrip():
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "ra.db"))
    db.initialize()
    db.save_reorg_assessment({
        "assess_id": "abc123",
        "kind": "risk",
        "timestamp": 1700000000,
        "risk": 0.1,
        "confirmations": 6,
    })
    rows = db.get_reorg_assessments(limit=5)
    assert len(rows) == 1
    assert rows[0]["assess_id"] == "abc123"
    assert rows[0]["risk"] == 0.1
