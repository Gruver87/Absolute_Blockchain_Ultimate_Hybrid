"""Catch-up gate orchestrator — pure refuse decisions (ADR 0003 Step C).

I/O (TCP solicit / import) stays on P2P; this module consolidates policy gates
so ``_sync_with_peer`` is a thin adapter over ports + policy.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from sync.catchup.policy import CatchUpPolicy


class CatchUpOrchestrator:
    """Consistency-aware catch-up refuse gates (no sockets)."""

    __slots__ = ("_policy",)

    def __init__(self, policy: Optional[CatchUpPolicy] = None) -> None:
        self._policy = policy if policy is not None else CatchUpPolicy()

    @property
    def policy(self) -> CatchUpPolicy:
        return self._policy

    def ahead_refuse_reason(
        self,
        *,
        local_height: int,
        peer_height: int,
        peer_head: str,
        local_block_for_head: Any = None,
        require_head: bool = True,
    ) -> str:
        return self._policy.ahead_refuse_reason(
            local_height=local_height,
            peer_height=peer_height,
            peer_head=peer_head,
            local_block_for_head=local_block_for_head,
            require_head=require_head,
        )

    def height_continuity_refuse_reason(
        self,
        block_data: Mapping[str, Any],
        expected_height: int,
        *,
        enabled: bool = True,
    ) -> str:
        return self._policy.height_continuity_refuse_reason(
            block_data, expected_height, enabled=enabled
        )

    def contiguous_parent_refuse_reason(
        self,
        block_data: Mapping[str, Any],
        expected_parent: str,
        *,
        enabled: bool = True,
    ) -> str:
        return self._policy.contiguous_parent_refuse_reason(
            block_data, expected_parent, enabled=enabled
        )

    def tip_head_refuse_reason(
        self,
        *,
        local_head: str,
        peer_head: str,
        enabled: bool = True,
    ) -> str:
        return self._policy.tip_head_refuse_reason(
            local_head=local_head,
            peer_head=peer_head,
            enabled=enabled,
        )

    def tip_head_at_height_refuse_reason(
        self,
        *,
        local_height: int,
        peer_height: int,
        local_head: str,
        peer_head: str,
        enabled: bool = True,
    ) -> str:
        """Only bind tip digest when local height exactly matches peer height."""
        if not enabled:
            return ""
        try:
            tip_h = int(local_height or 0)
            peer_h = int(peer_height or 0)
        except (TypeError, ValueError):
            return ""
        if tip_h <= 0 or peer_h <= 0 or tip_h != peer_h:
            return ""
        return self.tip_head_refuse_reason(
            local_head=local_head, peer_head=peer_head, enabled=True
        )
