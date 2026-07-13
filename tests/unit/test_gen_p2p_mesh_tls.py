#!/usr/bin/env python3
"""Tests for prod mesh P2P TLS generator."""

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def _load():
    path = os.path.join(ROOT, "scripts", "gen_p2p_mesh_tls.py")
    spec = importlib.util.spec_from_file_location("gen_p2p_mesh_tls", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_gen_p2p_mesh_tls_module():
    mod = _load()
    assert hasattr(mod, "generate_mesh_tls")
    assert mod.DEFAULT_NODES == (
        "docker-prod-mesh-1",
        "docker-prod-mesh-2",
        "docker-prod-mesh-3",
    )


def test_generate_mesh_tls_creates_node_dirs(tmp_path):
    mod = _load()
    dirs, backend = mod.generate_mesh_tls(
        tmp_path,
        ["test-node-a", "test-node-b"],
        force=True,
    )
    assert backend in ("openssl", "cryptography")
    assert set(dirs.keys()) == {"node1", "node2"}
    for name in ("node1", "node2"):
        node_dir = dirs[name]
        assert (node_dir / "node.pem").is_file()
        assert (node_dir / "node.key").is_file()
        assert (node_dir / "ca.pem").is_file()
