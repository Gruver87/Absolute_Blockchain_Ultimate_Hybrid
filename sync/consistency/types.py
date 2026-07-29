"""Immutable value types for sync consistency (ADR 0003)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Tuple


class ConsistencyState(str, Enum):
    """Fail-closed consistency machine states."""

    UNKNOWN = "unknown"
    PROBING = "probing"
    BEHIND_OPEN = "behind_open"
    CONSISTENT = "consistent"
    LOCKED_DOWN = "locked_down"


class ConsistencyOutcome(str, Enum):
    """Decision outcome for callers (mining / ready / catch-up)."""

    ALLOW_TRUSTED = "allow_trusted"
    ALLOW_CATCH_UP = "allow_catch_up"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PeerSyncView:
    """Immutable peer tip view for sync policy."""

    peer_id: str
    height: int = 0
    head_hash: str = ""
    dial_key: str = ""


@dataclass(frozen=True, slots=True)
class WireProbeResult:
    """Result of a solicited peer state_root probe."""

    probed: bool
    ok: Optional[bool]
    wire_roots: Tuple[Any, ...] = ()
    mismatch_peers: Tuple[str, ...] = ()
    detail: str = ""

    @staticmethod
    def never_probed(detail: str = "") -> "WireProbeResult":
        return WireProbeResult(probed=False, ok=None, detail=detail)

    @staticmethod
    def failed(detail: str = "") -> "WireProbeResult":
        return WireProbeResult(probed=True, ok=False, detail=detail)

    @staticmethod
    def succeeded(
        wire_roots: Tuple[Any, ...] = (),
        mismatch_peers: Tuple[str, ...] = (),
        detail: str = "",
    ) -> "WireProbeResult":
        return WireProbeResult(
            probed=True,
            ok=True,
            wire_roots=wire_roots,
            mismatch_peers=mismatch_peers,
            detail=detail,
        )


@dataclass(frozen=True, slots=True)
class ConsistencySnapshot:
    """Authoritative consistency snapshot (single-writer store)."""

    state: ConsistencyState = ConsistencyState.UNKNOWN
    consistent: bool = False
    probe: WireProbeResult = field(default_factory=WireProbeResult.never_probed)
    reason_code: str = "boot"
    updated_at: float = 0.0
    lockdown_total: int = 0


@dataclass(frozen=True, slots=True)
class ConsistencyDecision:
    """Policy decision derived from a snapshot / transition."""

    outcome: ConsistencyOutcome
    state: ConsistencyState
    reason_code: str
    may_mine: bool = False
    may_serve_as_synced: bool = False
    may_catch_up: bool = False
    consistent: bool = False

    @property
    def trusted(self) -> bool:
        return self.outcome is ConsistencyOutcome.ALLOW_TRUSTED and self.consistent
