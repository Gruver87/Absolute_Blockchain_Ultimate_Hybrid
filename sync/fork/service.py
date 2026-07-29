"""ForkReconcileService — same-height / to-head reconcile over ports (ADR 0005).

No ``asyncio``, no P2P node imports. I/O lives behind ForkReconcile* ports.

Malicious same-height bodies are **fail-closed**: evidence is emitted, the peer
is struck, and ``ForkReconcileMaliciousError`` is raised immediately.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from sync.fork.evidence import (
    ForkReconcileMaliciousError,
    ForkSecurityEvidence,
    build_evidence,
    is_malicious_refuse,
)
from sync.fork.policy import ForkReconcilePolicy
from sync.fork.types import (
    ForkPeerView,
    ForkReconcileConfig,
    ForkReconcileOutcome,
    ForkReconcileStatus,
)
from sync.ports import (
    ForkReconcileChainPort,
    ForkReconcileFetchPort,
    ForkReconcileProbePort,
    ForkReconcileSideEffectPort,
)

logger = logging.getLogger("Sync.Fork.Reconcile")

# After this many malicious same-height attempts from one peer → spam escalate.
_SPAM_THRESHOLD = 3


def _block_height(block: Mapping[str, Any], default: int = -1) -> int:
    try:
        return int(block.get("height", block.get("number", default)) or default)
    except (TypeError, ValueError):
        return int(default)


def _block_hash(block: Mapping[str, Any]) -> str:
    return str(block.get("hash") or block.get("block_hash") or "").strip()


class ForkReconcileService:
    """Same-height fork reconcile + generic to-head reorg via port façades."""

    __slots__ = ("_chain", "_fetch", "_probe", "_side", "_policy")

    def __init__(
        self,
        chain: ForkReconcileChainPort,
        fetch: ForkReconcileFetchPort,
        probe: ForkReconcileProbePort,
        side: ForkReconcileSideEffectPort,
        policy: Optional[ForkReconcilePolicy] = None,
    ) -> None:
        self._chain = chain
        self._fetch = fetch
        self._probe = probe
        self._side = side
        self._policy = policy if policy is not None else ForkReconcilePolicy()

    @property
    def policy(self) -> ForkReconcilePolicy:
        return self._policy

    def run_same_height(
        self,
        peer: ForkPeerView,
        config: Optional[ForkReconcileConfig] = None,
    ) -> ForkReconcileOutcome:
        """Reconcile when peer height == local and heads differ (GHOST preferred).

        Raises ``ForkReconcileMaliciousError`` on fail-closed hostile bodies.
        """
        cfg = config if config is not None else ForkReconcileConfig()
        try:
            return self._run_same_height_inner(peer, cfg)
        except ForkReconcileMaliciousError:
            raise
        except Exception as exc:
            logger.exception(
                "[Fork] run_same_height error peer=%s", (peer.peer_id or "")[:12]
            )
            return ForkReconcileOutcome.error(
                "fork_reconcile_exception",
                local_height=int(self._chain.height() or 0),
                target_head=str(peer.head_hash or ""),
                detail=str(exc),
            )

    def run_to_head(
        self,
        target_head: str,
        peer_hint: Optional[ForkPeerView] = None,
        config: Optional[ForkReconcileConfig] = None,
        *,
        ghost_probe: bool = False,
    ) -> ForkReconcileOutcome:
        """Fetch ``target_head``, policy-gate, reorg+import, tip-head bind.

        Raises ``ForkReconcileMaliciousError`` on fail-closed hostile bodies.
        """
        cfg = config if config is not None else ForkReconcileConfig()
        try:
            return self._run_to_head_inner(
                str(target_head or "").strip(),
                peer_hint,
                cfg,
                ghost_probe=bool(ghost_probe),
            )
        except ForkReconcileMaliciousError:
            raise
        except Exception as exc:
            logger.exception("[Fork] run_to_head error target=%s", str(target_head)[:16])
            return ForkReconcileOutcome.error(
                "fork_reconcile_exception",
                local_height=int(self._chain.height() or 0),
                target_head=str(target_head or ""),
                detail=str(exc),
            )

    def _fail_closed(
        self,
        reason: str,
        *,
        peer_id: str,
        local_height: int,
        target_head: str = "",
        block: Optional[Mapping[str, Any]] = None,
        detail: str = "",
    ) -> None:
        """Bump, emit Evidence, strike peer, raise — never soft-continue."""
        reason_code = str(reason or "refused")
        attempts = int(self._side.note_malicious_attempt(peer_id, reason_code) or 1)
        if attempts >= _SPAM_THRESHOLD and reason_code != "fork_same_height_spam":
            reason_code = "fork_same_height_spam"
            self._side.bump_refuse(reason_code)
            attempts = int(
                self._side.note_malicious_attempt(peer_id, reason_code) or attempts
            )
        else:
            self._side.bump_refuse(reason_code)

        evidence = build_evidence(
            reason_code=reason_code,
            peer_id=peer_id,
            local_height=int(local_height),
            target_head=str(target_head or ""),
            block=block,
            detail=str(detail or ""),
            attempt_count=attempts,
        )
        self._side.emit_security_evidence(evidence)
        self._side.strike_malicious_peer(peer_id, reason_code)
        outcome = ForkReconcileOutcome.refused(
            reason_code,
            local_height=int(local_height),
            target_head=str(target_head or ""),
            detail=str(detail or evidence.detail or ""),
        )
        raise ForkReconcileMaliciousError(outcome, evidence)

    def _refuse_or_fail_closed(
        self,
        reason: str,
        *,
        peer_id: str,
        local_height: int,
        target_head: str = "",
        block: Optional[Mapping[str, Any]] = None,
    ) -> ForkReconcileOutcome:
        if is_malicious_refuse(reason):
            self._fail_closed(
                reason,
                peer_id=peer_id,
                local_height=local_height,
                target_head=target_head,
                block=block,
            )
        self._side.bump_refuse(reason)
        return ForkReconcileOutcome.refused(
            reason, local_height=local_height, target_head=target_head
        )

    def _run_same_height_inner(
        self, peer: ForkPeerView, cfg: ForkReconcileConfig
    ) -> ForkReconcileOutcome:
        local_h = int(self._chain.height() or 0)
        local_head = str(self._chain.head() or "").strip()
        peer_head = str(peer.head_hash or "").strip()
        peer_id = str(peer.peer_id or "")

        if bool(cfg.prefer_ghost):
            ghost = str(self._side.ghost_canonical_head() or "").strip()
            if ghost and ghost.lower() != local_head.lower():
                ghost_out = self._run_to_head_inner(
                    ghost, peer, cfg, ghost_probe=bool(cfg.ghost_probe_enabled)
                )
                if ghost_out.status is ForkReconcileStatus.COMPLETE:
                    return ghost_out

        if not peer_head or (
            local_head and peer_head.lower() == local_head.lower()
        ):
            return ForkReconcileOutcome.skipped(
                local_height=local_h,
                target_head=peer_head or local_head,
                reason_code="same_head",
            )

        if bool(cfg.fork_probe_enabled):
            refuse = str(self._probe.fork_peer_head_probe_refuse(peer) or "")
            if refuse:
                return self._refuse_or_fail_closed(
                    refuse,
                    peer_id=peer_id,
                    local_height=local_h,
                    target_head=peer_head,
                )

        self._side.on_progress(
            f"Fork at #{peer.height}: local={local_head[:12]} peer={peer_head[:12]}"
        )
        return self._run_to_head_inner(peer_head, peer, cfg, ghost_probe=False)

    def _run_to_head_inner(
        self,
        target_head: str,
        peer_hint: Optional[ForkPeerView],
        cfg: ForkReconcileConfig,
        *,
        ghost_probe: bool,
    ) -> ForkReconcileOutcome:
        local_h = int(self._chain.height() or 0)
        target = str(target_head or "").strip()
        peer_id = str(peer_hint.peer_id if peer_hint is not None else "")
        if not target:
            return ForkReconcileOutcome.refused(
                "empty_target_head", local_height=local_h
            )

        local_head = str(self._chain.head() or "").strip()
        if local_head and local_head.lower() == target.lower():
            return ForkReconcileOutcome.skipped(
                local_height=local_h, target_head=target, reason_code="already_at_head"
            )

        if ghost_probe:
            refuse = str(
                self._probe.ghost_head_probe_refuse(
                    target, peer_hint if peer_hint is not None else None
                )
                or ""
            )
            if refuse:
                return self._refuse_or_fail_closed(
                    refuse,
                    peer_id=peer_id,
                    local_height=local_h,
                    target_head=target,
                )

        peer_block, sourced_peer = self._fetch_target_block(
            target, peer_hint, float(cfg.fetch_timeout)
        )
        if peer_block is None:
            self._side.on_progress(
                f"Could not fetch head block {target[:12]} for reconcile"
            )
            return ForkReconcileOutcome.fetch_failed(
                local_height=local_h, target_head=target
            )
        if sourced_peer:
            peer_id = sourced_peer

        # Tip-safety evidence gate before soft ownership binds / reorg.
        tip_ev = str(self._side.tip_evidence_refuse(peer_block) or "")
        if tip_ev:
            reason = (
                tip_ev
                if is_malicious_refuse(tip_ev)
                else "tip_evidence_enforce_refuse"
            )
            return self._refuse_or_fail_closed(
                reason,
                peer_id=peer_id,
                local_height=local_h,
                target_head=target,
                block=peer_block,
            )

        refuse = self._policy.fetched_head_refuse_reason(
            target, peer_block, enabled=bool(cfg.head_hash_bind)
        )
        if refuse:
            return self._refuse_or_fail_closed(
                refuse,
                peer_id=peer_id,
                local_height=local_h,
                target_head=target,
                block=peer_block,
            )

        tip_h = int(self._chain.height() or 0)
        local_tip = str(self._chain.head() or "")
        refuse = self._policy.contiguous_parent_refuse_reason(
            peer_block,
            tip_height=tip_h,
            local_tip=local_tip,
            enabled=bool(cfg.contiguous_parent_bind),
        )
        if refuse:
            return self._refuse_or_fail_closed(
                refuse,
                peer_id=peer_id,
                local_height=tip_h,
                target_head=target,
                block=peer_block,
            )

        local_parent = str(self._chain.expected_parent(tip_h) or "")
        refuse = self._policy.same_height_parent_refuse_reason(
            peer_block,
            tip_height=tip_h,
            local_tip=local_tip,
            local_parent=local_parent,
            enabled=bool(cfg.same_height_parent_bind),
        )
        if refuse:
            return self._refuse_or_fail_closed(
                refuse,
                peer_id=peer_id,
                local_height=tip_h,
                target_head=target,
                block=peer_block,
            )

        block_h = _block_height(peer_block, 0)
        parent_hash = str(peer_block.get("parent_hash") or "")
        ancestor = self._chain.find_ancestor_height(parent_hash)
        if ancestor is None:
            self._side.on_progress("No common ancestor for target head")
            return ForkReconcileOutcome.no_ancestor(
                local_height=tip_h, target_head=target
            )

        rollback_to = min(int(ancestor), int(block_h) - 1)
        self._side.note_reorg_risk()

        if not self._chain.reorg_and_import(int(rollback_to), peer_block):
            self._side.on_progress("Failed to reorg/import target head")
            return ForkReconcileOutcome.import_failed(
                local_height=int(self._chain.height() or 0), target_head=target
            )

        tip_refuse = self._policy.tip_head_refuse_reason(
            target,
            str(self._chain.head() or ""),
            enabled=bool(cfg.tip_head_bind),
        )
        if tip_refuse:
            # Post-import tip drift is integrity refuse, not necessarily spam —
            # still bump, but only fail-closed if classified malicious.
            return self._refuse_or_fail_closed(
                tip_refuse,
                peer_id=peer_id,
                local_height=int(self._chain.height() or 0),
                target_head=target,
                block=peer_block,
            )

        sourced = sourced_peer or (peer_hint.peer_id if peer_hint else "")
        if sourced:
            self._side.set_peer_tip(
                sourced,
                int(block_h),
                _block_hash(peer_block) or target,
            )

        self._side.on_progress(
            f"Reorg complete — head={target[:12]} height=#{block_h}"
        )
        return ForkReconcileOutcome.complete(
            local_height=int(self._chain.height() or 0),
            target_head=target,
        )

    def _fetch_target_block(
        self,
        target: str,
        peer_hint: Optional[ForkPeerView],
        timeout: float,
    ) -> tuple[Optional[Mapping[str, Any]], str]:
        """Try hint peer, then peers claiming head, then all peers."""
        tried: set[str] = set()
        order: list[str] = []
        if peer_hint is not None and peer_hint.peer_id:
            hint_head = str(peer_hint.head_hash or "").strip()
            if not hint_head or hint_head.lower() == target.lower():
                order.append(peer_hint.peer_id)
        for pid in self._side.peer_ids_for_head(target):
            if pid and pid not in order:
                order.append(str(pid))
        for pid in self._side.all_peer_ids():
            if pid and pid not in order:
                order.append(str(pid))

        for pid in order:
            if pid in tried:
                continue
            tried.add(pid)
            blk = self._fetch.fetch_block_by_hash(
                pid, target, timeout=float(timeout)
            )
            if isinstance(blk, Mapping):
                return blk, pid
        return None, ""
