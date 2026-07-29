"""P2P transport boundary (ADR 0002 steps A–B).

Isolates native transport/admit from tip/sync/mempool. Live ``P2PNode`` rewire
is step C (separate approval).

Public API::

    from network.transport import (
        NativeTransportAdapter,
        PeerEndpoint,
        AdmitDecision,
        classify_reason,
        TransportRejectClass,
    )
"""

from __future__ import annotations

from network.transport.errors import (
    TransportCapabilityError,
    TransportError,
    TransportIoError,
    TransportValidationError,
)
from network.transport.native_adapter import NativeTransportAdapter, default_allowed_types
from network.transport.reject import RejectCounters, classify_reason, make_reject
from network.transport.types import (
    AdmitDecision,
    InboundFrame,
    OutboundEnvelope,
    PeerEndpoint,
    TransportReject,
    TransportRejectClass,
)

__all__ = [
    "AdmitDecision",
    "InboundFrame",
    "NativeTransportAdapter",
    "OutboundEnvelope",
    "PeerEndpoint",
    "RejectCounters",
    "TransportCapabilityError",
    "TransportError",
    "TransportIoError",
    "TransportReject",
    "TransportRejectClass",
    "TransportValidationError",
    "classify_reason",
    "default_allowed_types",
    "make_reject",
]
