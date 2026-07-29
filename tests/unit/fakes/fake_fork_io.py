"""In-memory ForkReconcile* port façade for ADR 0005 unit tests."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence


class FakeForkReconcileIO:
    """Implements Chain + Fetch + Probe + SideEffect in one object."""

    def __init__(
        self,
        *,
        height: int = 5,
        head: str = "local_tip",
        expected_parent: str = "parent_aa",
        blocks_by_hash: Optional[Dict[str, dict]] = None,
        ancestors: Optional[Dict[str, int]] = None,
        fetch_by_hash: Optional[Dict[str, Optional[dict]]] = None,
        fork_probe_refuse: str = "",
        ghost_probe_refuse: str = "",
        ghost_head: str = "",
        reorg_ok: bool = True,
        tip_after_reorg: Optional[str] = None,
        tip_evidence_refuse: str = "",
        running: bool = True,
    ) -> None:
        self._height = int(height)
        self._head = str(head or "")
        self._expected_parent = str(expected_parent or "")
        self._by_hash = dict(blocks_by_hash or {})
        self._ancestors = dict(ancestors or {})
        self._fetch = dict(fetch_by_hash or {})
        self._fork_probe_refuse = str(fork_probe_refuse or "")
        self._ghost_probe_refuse = str(ghost_probe_refuse or "")
        self._ghost_head = str(ghost_head or "")
        self._reorg_ok = bool(reorg_ok)
        self._tip_after_reorg = tip_after_reorg
        self._tip_evidence_refuse = str(tip_evidence_refuse or "")
        self._running = bool(running)
        self.refuses: List[str] = []
        self.progress: List[str] = []
        self.reorg_calls: List[tuple] = []
        self.fetch_calls: List[tuple] = []
        self.peer_tips: Dict[str, tuple] = {}
        self.evidence: List[Any] = []
        self.strikes: List[tuple] = []
        self.malicious_attempts: Dict[str, int] = {}

    # ── Chain ────────────────────────────────────────────────────────────────

    def height(self) -> int:
        return int(self._height)

    def head(self) -> str:
        return str(self._head or "")

    def expected_parent(self, height: int) -> str:
        return str(self._expected_parent or "")

    def get_block(self, height_or_hash: Any) -> Any:
        key = str(height_or_hash or "").strip()
        return self._by_hash.get(key)

    def find_ancestor_height(self, parent_hash: str) -> Optional[int]:
        key = str(parent_hash or "").strip()
        if key in self._ancestors:
            return int(self._ancestors[key])
        return None

    def reorg_and_import(self, rollback_to: int, block: Mapping[str, Any]) -> bool:
        self.reorg_calls.append((int(rollback_to), dict(block)))
        if not self._reorg_ok:
            return False
        hh = str(block.get("hash") or block.get("block_hash") or "").strip()
        try:
            h = int(block.get("height", block.get("number", self._height)) or self._height)
        except (TypeError, ValueError):
            h = self._height
        self._height = h
        if self._tip_after_reorg is not None:
            self._head = str(self._tip_after_reorg)
        else:
            self._head = hh
        if hh:
            self._by_hash[hh] = dict(block)
        return True

    # ── Fetch ────────────────────────────────────────────────────────────────

    def fetch_block_by_hash(
        self,
        peer_id: str,
        block_hash: str,
        *,
        timeout: float = 30.0,
    ) -> Optional[Mapping[str, Any]]:
        self.fetch_calls.append((str(peer_id), str(block_hash), float(timeout)))
        key = str(block_hash or "").strip()
        if key in self._fetch:
            return self._fetch[key]
        return self._by_hash.get(key)

    # ── Probe ────────────────────────────────────────────────────────────────

    def fork_peer_head_probe_refuse(self, peer: Any) -> str:
        return str(self._fork_probe_refuse or "")

    def ghost_head_probe_refuse(self, ghost_head: str, peer_hint: Any = None) -> str:
        return str(self._ghost_probe_refuse or "")

    # ── Side effects ─────────────────────────────────────────────────────────

    def bump_refuse(self, reason: str) -> None:
        self.refuses.append(str(reason or ""))

    def set_peer_tip(self, peer_id: str, height: int, head_hash: str) -> None:
        self.peer_tips[str(peer_id)] = (int(height), str(head_hash))

    def ghost_canonical_head(self) -> str:
        return str(self._ghost_head or "")

    def peer_ids_for_head(self, head_hash: str) -> Sequence[str]:
        return ["peer-1"]

    def all_peer_ids(self) -> Sequence[str]:
        return ["peer-1"]

    def note_reorg_risk(self) -> None:
        return None

    def is_running(self) -> bool:
        return bool(self._running)

    def on_progress(self, message: str) -> None:
        self.progress.append(str(message or ""))

    def tip_evidence_refuse(self, block: Mapping[str, Any]) -> str:
        return str(self._tip_evidence_refuse or "")

    def note_malicious_attempt(self, peer_id: str, reason: str) -> int:
        peer_key = str(peer_id or "")
        n = int(self.malicious_attempts.get(peer_key, 0) or 0) + 1
        self.malicious_attempts[peer_key] = n
        return n

    def emit_security_evidence(self, evidence: Any) -> None:
        self.evidence.append(evidence)

    def strike_malicious_peer(self, peer_id: str, reason: str) -> bool:
        self.strikes.append((str(peer_id), str(reason)))
        return False
