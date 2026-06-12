# -*- coding: utf-8 -*-
"""Peer discovery for legacy tests."""
from typing import List, Optional


class Discovery:
    def __init__(self, peer_manager, p2p_server):
        self.peer_manager = peer_manager
        self.p2p_server = p2p_server
        self._bootstrap: List[str] = []

    def add_bootstrap_node(self, address: str) -> None:
        self._bootstrap.append(address)

    def get_bootstrap_count(self) -> int:
        return len(self._bootstrap)
