"""Catch-up Path A value types (ADR 0004). No P2P imports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CatchUpStatus(str, Enum):
    SKIPPED = "skipped"
    REFUSED = "refused"
    STALLED = "stalled"
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass(frozen=True)
class CatchUpPeerView:
    """Immutable peer tip view for Path A (no sockets)."""

    peer_id: str
    height: int
    head_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "peer_id", str(self.peer_id or ""))
        object.__setattr__(self, "height", int(self.height or 0))
        object.__setattr__(self, "head_hash", str(self.head_hash or "").strip())


@dataclass(frozen=True)
class CatchUpConfig:
    """Feature flags / knobs for Path A ahead catch-up."""

    batch_size: int = 32
    require_head: bool = True
    tip_head_bind: bool = True
    height_continuity_bind: bool = True
    contiguous_parent_bind: bool = True
    tip_probe_enabled: bool = True
    peer_head_probe_enabled: bool = True
    fetch_timeout: float = 45.0

    def __post_init__(self) -> None:
        bs = int(self.batch_size or 1)
        if bs < 1:
            bs = 1
        object.__setattr__(self, "batch_size", bs)
        object.__setattr__(self, "fetch_timeout", float(self.fetch_timeout or 45.0))


@dataclass(frozen=True)
class CatchUpOutcome:
    """Result of ``CatchUpPathAService.run_ahead``."""

    status: CatchUpStatus
    reason_code: str = ""
    local_height: int = 0
    target_height: int = 0
    imported: int = 0
    reached_target: bool = False
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is CatchUpStatus.COMPLETE

    @classmethod
    def skipped(
        cls,
        *,
        local_height: int,
        target_height: int,
        reason_code: str = "not_ahead",
    ) -> "CatchUpOutcome":
        return cls(
            status=CatchUpStatus.SKIPPED,
            reason_code=reason_code,
            local_height=int(local_height),
            target_height=int(target_height),
        )

    @classmethod
    def refused(
        cls,
        reason_code: str,
        *,
        local_height: int,
        target_height: int,
        detail: str = "",
    ) -> "CatchUpOutcome":
        return cls(
            status=CatchUpStatus.REFUSED,
            reason_code=str(reason_code or "refused"),
            local_height=int(local_height),
            target_height=int(target_height),
            detail=str(detail or ""),
        )

    @classmethod
    def stalled(
        cls,
        *,
        local_height: int,
        target_height: int,
        imported: int = 0,
        reason_code: str = "fetch_stall",
        detail: str = "",
    ) -> "CatchUpOutcome":
        return cls(
            status=CatchUpStatus.STALLED,
            reason_code=reason_code,
            local_height=int(local_height),
            target_height=int(target_height),
            imported=int(imported),
            detail=str(detail or ""),
        )

    @classmethod
    def incomplete(
        cls,
        *,
        local_height: int,
        target_height: int,
        imported: int = 0,
        reason_code: str = "incomplete",
        detail: str = "",
    ) -> "CatchUpOutcome":
        return cls(
            status=CatchUpStatus.INCOMPLETE,
            reason_code=reason_code,
            local_height=int(local_height),
            target_height=int(target_height),
            imported=int(imported),
            reached_target=False,
            detail=str(detail or ""),
        )

    @classmethod
    def complete(
        cls,
        *,
        local_height: int,
        target_height: int,
        imported: int = 0,
        reason_code: str = "ok",
    ) -> "CatchUpOutcome":
        return cls(
            status=CatchUpStatus.COMPLETE,
            reason_code=reason_code,
            local_height=int(local_height),
            target_height=int(target_height),
            imported=int(imported),
            reached_target=True,
        )

    @classmethod
    def error(
        cls,
        reason_code: str,
        *,
        local_height: int = 0,
        target_height: int = 0,
        imported: int = 0,
        detail: str = "",
    ) -> "CatchUpOutcome":
        return cls(
            status=CatchUpStatus.ERROR,
            reason_code=str(reason_code or "error"),
            local_height=int(local_height),
            target_height=int(target_height),
            imported=int(imported),
            detail=str(detail or ""),
        )
