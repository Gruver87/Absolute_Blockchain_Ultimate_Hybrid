"""Wave 60 — bridge relayer proof API + mock L1."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


class _FakeCfg:
    bridge_enabled = True
    bridge_mode = "simulator"
    bridge_oracle_secret = "wave60-secret"
    bridge_l1_queue_path = "data/bridge_l1_queue.json"


class _FakeDB:
    def get_bridge_locks(self, limit=1000):
        return [{"tx_hash": "0xlock", "status": "pending"}]


class _FakeBridge:
    def lock_and_bridge(self, *a, **k):
        return {"tx_hash": "0xlock"}


def test_bridge_relayer_proof_api(monkeypatch):
    from api.http import _build_testnet_bridge_relayer_proof

    monkeypatch.setenv("ETH_RPC_URL", "http://127.0.0.1:19445")
    out = _build_testnet_bridge_relayer_proof(_FakeCfg(), _FakeDB(), _FakeBridge())
    assert out["api_wave"] == 60
    assert out["proof_ok"] is True
    assert out["eth_rpc_configured"] is True
    assert out["oracle_hmac_configured"] is True
