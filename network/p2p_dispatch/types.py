"""Typed results for the P2P application dispatcher."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DispatchOutcome(str, Enum):
    """Result of application-level message routing."""

    HANDLED = "handled"
    UNHANDLED = "unhandled"
    REFUSED = "refused"


@dataclass(frozen=True, slots=True)
class TipEvidenceDecision:
    """Result of tip-safety / tip-evidence evaluation at the wire layer.

    Attributes:
        ok: True when the candidate may proceed to the domain handler.
        reason_code: Stable machine code for metrics / strikes.
        detail: Optional human-readable context.
        enforce_refuse: True when enforce mode requires the dispatcher to stop.
    """

    ok: bool
    reason_code: str = "ok"
    detail: str = ""
    enforce_refuse: bool = False
