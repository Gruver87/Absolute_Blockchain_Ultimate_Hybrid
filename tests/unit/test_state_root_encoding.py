"""State-root encoding version scaffold."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_active_encoding_is_v1_float_contract():
    from runtime.state_root_encoding import active_state_root_encoding

    enc = active_state_root_encoding()
    assert enc["version"] == 1
    assert enc["name"] == "float_b_round12"
    assert enc["active"] is True
    assert enc["satoshi_tip_ready"] is False


def test_v2_request_blocked_without_migration():
    from runtime.config import Config
    from runtime.state_root_encoding import active_state_root_encoding

    cfg = Config()
    cfg.state_root_encoding_version = 2
    enc = active_state_root_encoding(cfg)
    assert enc["version"] == 2
    assert enc["active"] is False
    assert "blocked_reason" in enc


def test_blockchain_policy_includes_encoding(tmp_path):
    import os
    import tempfile

    from runtime.config import Config
    from storage.database import Database
    from core.blockchain import Blockchain

    fd, path = tempfile.mkstemp(suffix=".db", dir=tmp_path)
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    policy = bc.get_state_root_policy()
    assert policy["encoding"]["active"]["version"] == 1
    db.close()
    os.remove(path)


def test_state_root_encoding_endpoint(tmp_path):
    import json
    import os
    import tempfile
    import threading
    import time
    import urllib.request

    from api.http import RESTHandler, ThreadedHTTPServer, configure_rate_limiter
    from core.blockchain import Blockchain
    from runtime.config import Config
    from storage.database import Database

    fd, path = tempfile.mkstemp(suffix=".db", dir=tmp_path)
    os.close(fd)
    cfg = Config()
    cfg.db_path = path
    cfg.http_port = 15420
    cfg.deployment_mode = "dev"
    cfg.rate_limit_rpm = 120
    db = Database(path)
    db.initialize()
    bc = Blockchain(cfg, db)
    RESTHandler.config = cfg
    RESTHandler.blockchain = bc
    RESTHandler.db = db
    RESTHandler.mempool = None
    RESTHandler.p2p = None
    configure_rate_limiter(cfg)
    server = ThreadedHTTPServer(("127.0.0.1", cfg.http_port), RESTHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{cfg.http_port}/chain/state-root/encoding", timeout=5
        ) as resp:
            body = json.loads(resp.read().decode())
        assert body["active"]["version"] == 1
        assert body["active"]["active"] is True
        assert body["planned"]["version"] == 2
    finally:
        server.shutdown()
        db.close()
        os.remove(path)
