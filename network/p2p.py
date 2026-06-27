"""Compatibility shim — legacy imports expect network.p2p."""
from network.p2p_node import P2PNode

__all__ = ["P2PNode"]
