"""Typed errors for the P2P transport boundary.

Transport failures never become silent ``None`` without a reason code when
the adapter is used correctly: callers always receive either a success value
or a ``TransportError`` / structured reject decision.
"""

from __future__ import annotations


class TransportError(Exception):
    """Base class for transport-boundary failures.

    Attributes:
        code: Stable machine-readable reason (metrics / logs).
        message: Human-readable detail.
    """

    code: str = "transport_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        self.message = str(message)
        if code is not None:
            self.code = str(code)
        super().__init__(self.message)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


class TransportCapabilityError(TransportError):
    """Raised when abs_native transport/TLS capability is missing."""

    code = "transport_capability"


class TransportValidationError(TransportError):
    """Raised when adapter inputs violate structural invariants."""

    code = "transport_validation"


class TransportIoError(TransportError):
    """Raised when dial/listen/read/write fails at the socket layer."""

    code = "transport_io"
