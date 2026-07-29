"""Same-height fork reconcile value types (ADR 0005). No P2P imports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ForkReconcileStatus(str, Enum):
    SKIPPED = "skipped"
    REFUSED = "refused"
    FETCH_FAILED = "fetch_failed"
    NO_ANCESTOR = "no_ancestor"
    IMPORT_FAILED = "import_failed"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass(frozen=True)
class ForkPeerView:
    """Immutable peer tip view for fork reconcile (no sockets)."""

    peer_id: str
    height: int
    head_hash: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "peer_id", str(self.peer_id or ""))
        object.__setattr__(self, "height", int(self.height or 0))
        object.__setattr__(self, "head_hash", str(self.head_hash or "").strip())


@dataclass(frozen=True)
class ForkReconcileConfig:
    """Feature flags for same-height / to-head reconcile."""

    fork_probe_enabled: bool = True
    ghost_probe_enabled: bool = True
    prefer_ghost: bool = True
    head_hash_bind: bool = True
    contiguous_parent_bind: bool = True
    same_height_parent_bind: bool = True
    tip_head_bind: bool = True
    fetch_timeout: float = 30.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "fetch_timeout", float(self.fetch_timeout or 30.0))


@dataclass(frozen=True)
class ForkReconcileOutcome:
    """Result of ``ForkReconcileService`` operations."""

    status: ForkReconcileStatus
    reason_code: str = ""
    local_height: int = 0
    target_head: str = ""
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (
            ForkReconcileStatus.COMPLETE,
            ForkReconcileStatus.SKIPPED,
        )

    @classmethod
    def skipped(
        cls,
        *,
        local_height: int = 0,
        target_head: str = "",
        reason_code: str = "noop",
    ) -> "ForkReconcileOutcome":
        return cls(
            status=ForkReconcileStatus.SKIPPED,
            reason_code=reason_code,
            local_height=int(local_height),
            target_head=str(target_head or ""),
        )

    @classmethod
    def refused(
        cls,
        reason_code: str,
        *,
        local_height: int = 0,
        target_head: str = "",
        detail: str = "",
    ) -> "ForkReconcileOutcome":
        return cls(
            status=ForkReconcileStatus.REFUSED,
            reason_code=str(reason_code or "refused"),
            local_height=int(local_height),
            target_head=str(target_head or ""),
            detail=str(detail or ""),
        )

    @classmethod
    def fetch_failed(
        cls,
        *,
        local_height: int = 0,
        target_head: str = "",
        reason_code: str = "fetch_failed",
    ) -> "ForkReconcileOutcome":
        return cls(
            status=ForkReconcileStatus.FETCH_FAILED,
            reason_code=reason_code,
            local_height=int(local_height),
            target_head=str(target_head or ""),
        )

    @classmethod
    def no_ancestor(
        cls,
        *,
        local_height: int = 0,
        target_head: str = "",
    ) -> "ForkReconcileOutcome":
        return cls(
            status=ForkReconcileStatus.NO_ANCESTOR,
            reason_code="no_common_ancestor",
            local_height=int(local_height),
            target_head=str(target_head or ""),
        )

    @classmethod
    def import_failed(
        cls,
        *,
        local_height: int = 0,
        target_head: str = "",
        reason_code: str = "reorg_import_failed",
    ) -> "ForkReconcileOutcome":
        return cls(
            status=ForkReconcileStatus.IMPORT_FAILED,
            reason_code=reason_code,
            local_height=int(local_height),
            target_head=str(target_head or ""),
        )

    @classmethod
    def complete(
        cls,
        *,
        local_height: int = 0,
        target_head: str = "",
        reason_code: str = "ok",
    ) -> "ForkReconcileOutcome":
        return cls(
            status=ForkReconcileStatus.COMPLETE,
            reason_code=reason_code,
            local_height=int(local_height),
            target_head=str(target_head or ""),
        )

    @classmethod
    def error(
        cls,
        reason_code: str,
        *,
        local_height: int = 0,
        target_head: str = "",
        detail: str = "",
    ) -> "ForkReconcileOutcome":
        return cls(
            status=ForkReconcileStatus.ERROR,
            reason_code=str(reason_code or "error"),
            local_height=int(local_height),
            target_head=str(target_head or ""),
            detail=str(detail or ""),
        )
