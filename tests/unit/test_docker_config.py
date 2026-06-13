#!/usr/bin/env python3
"""Docker devnet JSON configs and CHAIN_ID env wiring."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.config import Config

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _load_json(name):
    path = os.path.join(ROOT, "docker", name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_docker_node_configs_parse():
    n1 = _load_json("node1.json")
    n2 = _load_json("node2.json")
    assert n1["chain_id"] == 77777
    assert n2["chain_id"] == 77777
    assert n1["bootstrap_peers"] == []
    assert n2["bootstrap_peers"] == ["node1:5000"]
    assert n2["mining_enabled"] is False


def test_config_from_docker_json_files():
    for name in ("node1.json", "node2.json"):
        cfg = Config.from_json(os.path.join(ROOT, "docker", name))
        assert cfg.chain_id == 77777
        assert cfg.rate_limit_rpm == 0


def test_chain_id_env_override():
    os.environ["CHAIN_ID"] = "99999"
    try:
        cfg = Config()
        cfg.apply_env()
        assert cfg.chain_id == 99999
    finally:
        os.environ.pop("CHAIN_ID", None)
