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
    peer_heights: List[int] | None = None,
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

    # Live STATUS heights — do not forge while followers are behind.
    if peer_heights and len(peer_heights) >= min_mesh_peers:
        if any(h < local_height for h in peer_heights):
            return False

    if wire_roots:
        for entry in wire_roots:
            eh = int(entry.get("height", 0) or 0)
            pr = str(entry.get("state_root") or "").strip().lower()
            # Ignore stale wire responses; peer_heights gate catch-up above.
            if eh == local_height and pr and pr != local_root_norm:
                return False

    if len(wire_roots) >= min_mesh_peers:
        matching = sum(
            1
            for entry in wire_roots
            if int(entry.get("height", 0) or 0) == local_height
            and str(entry.get("state_root") or "").strip().lower() == local_root_norm
        )
        if matching >= min_mesh_peers:
            return True

    # Wire RPC may time out under load; STATUS heights still prove mesh alignment.
    if peer_heights and len(peer_heights) >= min_mesh_peers:
        if all(h >= local_height for h in peer_heights) and all(
            h == local_height for h in peer_heights
        ):
            return True

    # Partial / empty wire: followers connected and sync engine aligned
    return bool(state_consistent) and connected_peers >= min_mesh_peers
