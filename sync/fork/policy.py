"""Pure fork-reconcile refuse predicates (ADR 0005). No I/O."""

from __future__ import annotations

from typing import Any, Mapping


def _block_height(block: Mapping[str, Any], default: int = -1) -> int:
    try:
        return int(block.get("height", block.get("number", default)) or default)
    except (TypeError, ValueError):
        return int(default)


def _block_hash(block: Mapping[str, Any]) -> str:
    return str(block.get("hash") or block.get("block_hash") or "").strip()


class ForkReconcilePolicy:
    """Soft ownership binds for same-height / to-head reconcile."""

    def fetched_head_refuse_reason(
        self,
        target_head: str,
        peer_block: Mapping[str, Any],
        *,
        enabled: bool = True,
    ) -> str:
        """Fetched body hash must match target_head."""
        if not enabled:
            return ""
        want = str(target_head or "").strip()
        if not want or not isinstance(peer_block, Mapping):
            return ""
        got = _block_hash(peer_block)
        if got and got.lower() != want.lower():
            return "reconcile_head_hash_mismatch"
        return ""

    def contiguous_parent_refuse_reason(
        self,
        peer_block: Mapping[str, Any],
        *,
        tip_height: int,
        local_tip: str,
        enabled: bool = True,
    ) -> str:
        """When body is tip+1, parent must cite local tip."""
        if not enabled or not isinstance(peer_block, Mapping):
            return ""
        body_h = _block_height(peer_block, -1)
        tip_h = int(tip_height or 0)
        if body_h < 0 or tip_h < 0 or body_h != tip_h + 1:
            return ""
        parent = str(peer_block.get("parent_hash") or "").strip()
        tip = str(local_tip or "").strip()
        if parent and tip and parent.lower() != tip.lower():
            return "reconcile_contiguous_parent_mismatch"
        return ""

    def same_height_parent_refuse_reason(
        self,
        peer_block: Mapping[str, Any],
        *,
        tip_height: int,
        local_tip: str,
        local_parent: str,
        enabled: bool = True,
    ) -> str:
        """Same-height sibling must share tip-height parent (not tip itself)."""
        if not enabled or not isinstance(peer_block, Mapping):
            return ""
        body_h = _block_height(peer_block, -1)
        tip_h = int(tip_height or 0)
        if body_h < 0 or tip_h < 0 or body_h != tip_h:
            return ""
        got_hash = _block_hash(peer_block)
        tip = str(local_tip or "").strip()
        if got_hash and tip and got_hash.lower() == tip.lower():
            return ""
        parent = str(peer_block.get("parent_hash") or "").strip()
        want_parent = str(local_parent or "").strip()
        if (
            parent
            and want_parent
            and want_parent != ("0" * 64)
            and parent.lower() != want_parent.lower()
        ):
            return "reconcile_same_height_parent_mismatch"
        return ""

    def tip_head_refuse_reason(
        self,
        target_head: str,
        local_tip: str,
        *,
        enabled: bool = True,
    ) -> str:
        """After import, local tip digest must match target_head."""
        if not enabled:
            return ""
        want = str(target_head or "").strip()
        if not want:
            return ""
        tip = str(local_tip or "").strip()
        if tip and tip.lower() != want.lower():
            return "reconcile_tip_head_mismatch"
        return ""
