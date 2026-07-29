"""Protocol ports between transport and application layers.

Implementations live in ``native_adapter`` (transport) or future dispatcher
modules (application). Domain code must depend on these protocols, not on
``P2PNode`` internals.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from network.transport.types import (
    AdmitDecision,
    InboundFrame,
    OutboundEnvelope,
    PeerEndpoint,
)


@runtime_checkable
class PeerAdmitPort(Protocol):
    """Admit a raw inbound NDJSON line into an application frame (or reject)."""

    def admit_inbound_line(
        self,
        line: bytes,
        *,
        peer_id: str,
        now: float,
        max_bytes: int = ...,
        allowed_types: Optional[list[str]] = ...,
        rate_table: Any = ...,
    ) -> AdmitDecision:
        """Parse + rate/bandwidth admit. Never raises on wire reject."""
        ...


@runtime_checkable
class PeerSendPort(Protocol):
    """Prepare an outbound application message for the wire."""

    def prepare_outbound(
        self,
        envelope: OutboundEnvelope,
        *,
        now: float,
        max_bytes: int = ...,
        allowed_types: Optional[list[str]] = ...,
        rate_table: Any = ...,
    ) -> AdmitDecision:
        """Encode + allowlist + egress admit.

        On success ``AdmitDecision.frame`` carries ``msg_type`` and raw payload
        bytes in ``data`` as ``{"payload": bytes}`` (adapter-defined).
        """
        ...


@runtime_checkable
class PeerEventPort(Protocol):
    """Application callback for admitted inbound frames (step C consumer)."""

    def on_inbound_frame(self, frame: InboundFrame) -> None:
        """Handle one admitted frame. Must not perform socket I/O."""
        ...


@runtime_checkable
class TransportCapabilityPort(Protocol):
    """Query native transport/TLS readiness."""

    def capability_status(self) -> Mapping[str, Any]:
        """Return capability flags (available, tls, error)."""
        ...

    def require_transport(self) -> None:
        """Raise ``TransportCapabilityError`` if native transport is missing."""
        ...


@runtime_checkable
class TransportDialPort(Protocol):
    """Outbound dial / inbound listen facade (opaque native handles)."""

    def connect(self, endpoint: PeerEndpoint, **kwargs: Any) -> Any:
        """Dial peer; returns opaque connection handle."""
        ...
