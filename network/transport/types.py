"""Immutable value types for the P2P transport ↔ application boundary.

These types must not import ``network.p2p_node`` or tip/sync/mempool domains.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional


class TransportRejectClass(str, Enum):
    """High-level reject class for metrics aggregation."""

    FRAME = "frame"
    RATE = "rate"
    WIRE_SHAPE = "wire_shape"
    WIRE_SEMANTIC = "wire_semantic"
    ADMIT = "admit"
    EGRESS = "egress"
    CAPABILITY = "capability"
    INTERNAL = "internal"
    OK = "ok"


@dataclass(frozen=True, slots=True)
class PeerEndpoint:
    """Remote peer network endpoint.

    Attributes:
        host: IP or hostname (no scheme).
        port: TCP port in 1..65535.
        peer_id: Optional logical peer id (empty until handshake).
    """

    host: str
    port: int
    peer_id: str = ""

    def __post_init__(self) -> None:
        from network.transport.errors import TransportValidationError

        if not isinstance(self.host, str) or not self.host.strip():
            raise TransportValidationError("host must be a non-empty string")
        if not isinstance(self.port, int) or isinstance(self.port, bool):
            raise TransportValidationError("port must be int")
        if self.port < 1 or self.port > 65535:
            raise TransportValidationError(f"port out of range: {self.port}")
        if not isinstance(self.peer_id, str):
            raise TransportValidationError("peer_id must be str")


@dataclass(frozen=True, slots=True)
class InboundFrame:
    """One admitted inbound NDJSON application message.

    Attributes:
        peer_id: Peer key used for rate/ban tables.
        msg_type: Wire ``type`` field.
        data: Decoded ``data`` payload (JSON-compatible).
        raw_len: Original line byte length (for cost accounting).
    """

    peer_id: str
    msg_type: str
    data: Any
    raw_len: int


@dataclass(frozen=True, slots=True)
class OutboundEnvelope:
    """Application → transport send request (pre-wire).

    Attributes:
        peer_id: Destination peer key.
        msg_type: Wire type.
        payload: Mapping or JSON-serializable body placed under ``data``.
    """

    peer_id: str
    msg_type: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TransportReject:
    """Structured transport reject (never raises into application hot path)."""

    reason_code: str
    reject_class: TransportRejectClass
    detail: str = ""


@dataclass(frozen=True, slots=True)
class AdmitDecision:
    """Result of ingress admit on a raw NDJSON line."""

    ok: bool
    frame: Optional[InboundFrame] = None
    reject: Optional[TransportReject] = None

    @property
    def accepted(self) -> bool:
        """True when ``frame`` is present and ok."""
        return bool(self.ok and self.frame is not None)
