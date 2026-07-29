"""Fork reconcile security evidence (ADR 0005). No P2P imports.

Fail-closed malicious same-height attempts produce a structured evidence
record for the security / EventBus surface.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from sync.fork.types import ForkReconcileOutcome


# Soft-ownership refuses that indicate a hostile/fake same-height body.
MALICIOUS_REFUSE_CODES = frozenset(
    {
        "reconcile_head_hash_mismatch",
        "reconcile_same_height_parent_mismatch",
        "reconcile_contiguous_parent_mismatch",
        "fork_peer_head_hash_mismatch",
        "fork_peer_head_parent_mismatch",
        "fork_peer_head_height_mismatch",
        "fork_same_height_spam",
        "tip_evidence_enforce_refuse",
    }
)


@dataclass(frozen=True)
class ForkSecurityEvidence:
    """Immutable security evidence for a fail-closed fork refuse."""

    reason_code: str
    peer_id: str
    local_height: int
    target_head: str = ""
    block_hash: str = ""
    block_height: int = -1
    detail: str = ""
    attempt_count: int = 1
    ts: float = field(default_factory=time.time)
    kind: str = "fork_same_height_malicious"

    def to_bus_payload(self) -> Mapping[str, Any]:
        return {
            "kind": self.kind,
            "reason_code": self.reason_code,
            "peer_id": self.peer_id,
            "local_height": int(self.local_height),
            "target_head": self.target_head,
            "block_hash": self.block_hash,
            "block_height": int(self.block_height),
            "detail": self.detail,
            "attempt_count": int(self.attempt_count),
            "ts": float(self.ts),
            "fail_closed": True,
        }


class ForkReconcileMaliciousError(Exception):
    """Raised when same-height reconcile fail-closes on a malicious peer body.

    Side effects (evidence + strike) are applied *before* this is raised.
    """

    def __init__(
        self,
        outcome: ForkReconcileOutcome,
        evidence: ForkSecurityEvidence,
    ) -> None:
        self.outcome = outcome
        self.evidence = evidence
        super().__init__(
            f"fail-closed fork refuse peer={evidence.peer_id[:12]} "
            f"reason={outcome.reason_code}"
        )


def is_malicious_refuse(reason_code: str) -> bool:
    return str(reason_code or "") in MALICIOUS_REFUSE_CODES


def build_evidence(
    *,
    reason_code: str,
    peer_id: str,
    local_height: int,
    target_head: str = "",
    block: Optional[Mapping[str, Any]] = None,
    detail: str = "",
    attempt_count: int = 1,
) -> ForkSecurityEvidence:
    bh = -1
    hh = ""
    if isinstance(block, Mapping):
        try:
            bh = int(block.get("height", block.get("number", -1)) or -1)
        except (TypeError, ValueError):
            bh = -1
        hh = str(block.get("hash") or block.get("block_hash") or "").strip()
    return ForkSecurityEvidence(
        reason_code=str(reason_code or "refused"),
        peer_id=str(peer_id or ""),
        local_height=int(local_height),
        target_head=str(target_head or ""),
        block_hash=hh,
        block_height=bh,
        detail=str(detail or ""),
        attempt_count=max(1, int(attempt_count or 1)),
    )
