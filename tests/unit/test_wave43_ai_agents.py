"""Wave 43 — AI Agent Manager SQLite persistence + plasma submit hint."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_ai_agent_create_persists_and_charges_fee():
    from features.ai_manager import AIAgentManager
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "ai.db"))
    db.initialize()
    owner = "0x" + "a" * 40
    db.set_balance(owner, 5.0)

    m1 = AIAgentManager(db=db)
    aid = m1.create_agent("Trader1", owner, "transformer")
    assert aid
    assert db.get_balance(owner) == 5.0 - m1.CREATE_FEE

    m2 = AIAgentManager(db=db)
    assert aid in m2.agents
    assert m2.get_stats()["persisted"] is True


def test_ai_agent_trade_persists_memory():
    from features.ai_manager import AIAgentManager
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "at.db"))
    db.initialize()
    owner = "0x" + "b" * 40
    db.set_balance(owner, 10.0)

    m = AIAgentManager(db=db)
    aid = m.create_agent("Bot", owner)
    out = m.trade(aid, "buy", 1.0, 100.0)
    assert out["success"] is True

    m2 = AIAgentManager(db=db)
    agent = m2.get_agent(aid)
    assert agent.actions_count == 1
    assert len(agent.memory) == 1


def test_ai_create_rejects_low_balance():
    from features.ai_manager import AIAgentManager
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "ar.db"))
    db.initialize()
    owner = "0x" + "c" * 40
    db.set_balance(owner, 0.001)

    m = AIAgentManager(db=db)
    assert m.create_agent("X", owner) is None
