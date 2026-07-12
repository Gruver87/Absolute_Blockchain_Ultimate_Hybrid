#!/usr/bin/env python3
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from runtime.mesh_mining import mesh_ready_for_mining


def test_mesh_ready_requires_connections():
    assert not mesh_ready_for_mining(
        min_mesh_peers=2,
        connected_peers=1,
        wire_roots=[],
        local_height=1,
        local_root="aa" * 32,
    )


def test_mesh_ready_partial_wire_when_consistent():
    root = "ab" * 32
    assert mesh_ready_for_mining(
        min_mesh_peers=2,
        connected_peers=2,
        wire_roots=[
            {"height": 1, "state_root": root},
            {"height": 1, "state_root": root},
        ],
        local_height=1,
        local_root=root,
        state_consistent=True,
    )


def test_mesh_ready_rejects_root_mismatch():
    assert not mesh_ready_for_mining(
        min_mesh_peers=2,
        connected_peers=2,
        wire_roots=[{"height": 1, "state_root": "cc" * 32}],
        local_height=1,
        local_root="ab" * 32,
        state_consistent=True,
        peer_heights=[1, 1],
    )


def test_mesh_ready_ignores_stale_wire_height():
    """Stale wire h=1 must not block hub at h=2 when STATUS peers are aligned."""
    root = "ab" * 32
    assert mesh_ready_for_mining(
        min_mesh_peers=2,
        connected_peers=2,
        wire_roots=[{"height": 1, "state_root": root}],
        local_height=2,
        local_root=root,
        state_consistent=False,
        peer_heights=[2, 2],
    )


def test_mesh_ready_empty_wire_not_consistent():
    assert not mesh_ready_for_mining(
        min_mesh_peers=2,
        connected_peers=2,
        wire_roots=[],
        local_height=1,
        local_root="ab" * 32,
        state_consistent=False,
    )


def test_mesh_ready_peer_heights_when_wire_slow():
    """Hub may forge when STATUS heights align even if wire_roots RPC timed out."""
    assert mesh_ready_for_mining(
        min_mesh_peers=2,
        connected_peers=2,
        wire_roots=[],
        local_height=2,
        local_root="ab" * 32,
        state_consistent=False,
        peer_heights=[2, 2],
    )


def test_mesh_ready_stale_peer_heights_wire_proves_alignment():
    """Stale P2P STATUS cache must not block when wire roots prove mesh alignment."""
    root = "ab" * 32
    assert mesh_ready_for_mining(
        min_mesh_peers=2,
        connected_peers=2,
        wire_roots=[
            {"height": 2, "state_root": root},
            {"height": 2, "state_root": root},
        ],
        local_height=2,
        local_root=root,
        state_consistent=False,
        peer_heights=[17, 17],
    )
