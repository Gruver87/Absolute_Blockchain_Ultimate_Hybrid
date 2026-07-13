#!/usr/bin/env python3
"""Cryptography-based P2P TLS generator tests."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_crypto():
    path = ROOT / "scripts" / "p2p_tls_crypto.py"
    spec = importlib.util.spec_from_file_location("p2p_tls_crypto", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_crypto_mesh_tls_generates_pems(tmp_path):
    mod = _load_crypto()
    dirs = mod.generate_mesh_tls_crypto(tmp_path, ["node-a", "node-b"], force=True)
    assert set(dirs) == {"node1", "node2"}
    assert (tmp_path / "ca.pem").is_file()
    for name in dirs:
        assert (dirs[name] / "node.pem").is_file()
        assert (dirs[name] / "node.key").is_file()
