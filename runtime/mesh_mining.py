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
    state_consistent: bool = False,
    peer_heights: List[int] | None = None,
) -> bool:
    """
    Return True when hub may forge the next block.

    Requires `min_mesh_peers` TCP links. Peer state_root RPC may return fewer
    responses than links (slow peer); STATUS height alignment is allowed only
    when `state_consistent` is already True (fail-closed). Wire tip matches
    alone may prove alignment without relying on the cached flag.
    """
    if min_mesh_peers <= 0:
        return True
    if connected_peers < min_mesh_peers:
        return False

    local_root_norm = (local_root or "").strip().lower()

    # Wire proof at local tip overrides stale P2P STATUS height cache.
    if wire_roots:
        for entry in wire_roots:
            eh = int(entry.get("height", 0) or 0)
            pr = str(entry.get("state_root") or "").strip().lower()
            if eh == local_height and pr and pr != local_root_norm:
                return False
        matching = sum(
            1
            for entry in wire_roots
            if int(entry.get("height", 0) or 0) == local_height
            and str(entry.get("state_root") or "").strip().lower() == local_root_norm
        )
        if matching >= min_mesh_peers:
            return True

    # Live STATUS heights — do not forge while followers are behind, and do not
    # forge on height alignment alone while state is known-inconsistent.
    if peer_heights and len(peer_heights) >= min_mesh_peers:
        if any(h < local_height for h in peer_heights):
            return False
        if all(h == local_height for h in peer_heights):
            return bool(state_consistent)

    return False
