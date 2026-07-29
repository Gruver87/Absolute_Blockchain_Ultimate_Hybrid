"""P2P application dispatcher (ADR 0002 Step D).

Isolates message-type routing from transport / ``_message_loop``.

Public API::

    from network.p2p_dispatch import (
        P2PDispatcher,
        HandlerRegistry,
        TipSafetyEvidenceBridge,
        build_default_dispatcher,
        DispatchOutcome,
    )
"""

from __future__ import annotations

from network.p2p_dispatch.dispatcher import (
    P2PDispatcher,
    build_default_dispatcher,
    build_default_registry,
    rebind_tip_handlers,
)
from network.p2p_dispatch.registry import HandlerRegistry
from network.p2p_dispatch.tip_evidence import TipSafetyEvidenceBridge
from network.p2p_dispatch.types import DispatchOutcome, TipEvidenceDecision

__all__ = [
    "DispatchOutcome",
    "HandlerRegistry",
    "P2PDispatcher",
    "TipEvidenceDecision",
    "TipSafetyEvidenceBridge",
    "build_default_dispatcher",
    "build_default_registry",
    "rebind_tip_handlers",
]
