#!/usr/bin/env python3
"""Prod mesh mining gate: peers connected + state alignment."""

from __future__ import annotations

from typing import Dict, List


def mesh_ready_for_mining(
    *,
    min_mesh_peers: int,
    connected_peers: int,
    wire_roots: List[Dict],
    local_height: int,
    local_root: str,
    state_consistent: bool = True,
) -> bool:
    """
    Return True when hub may forge the next block.

    Requires `min_mesh_peers` TCP links. Peer state_root RPC may return fewer
    responses than links (slow peer); in that case trust sync consistency when
    all returned roots match local height.
    """
    if min_mesh_peers <= 0:
        return True
    if connected_peers < min_mesh_peers:
        return False

    local_root_norm = (local_root or "").strip().lower()
    if wire_roots:
        for entry in wire_roots:
            eh = int(entry.get("height", 0) or 0)
            pr = str(entry.get("state_root") or "").strip().lower()
            if eh < local_height:
                return False
            if eh == local_height and pr and pr != local_root_norm:
                return False

    if len(wire_roots) >= min_mesh_peers:
        return True

    # Partial / empty wire: followers connected and sync engine aligned
    return bool(state_consistent) and connected_peers >= min_mesh_peers
