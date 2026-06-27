#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REORG PREDICTION ENGINE — risk scoring with SQLite history (Wave 45)."""

import hashlib
import math
import time
from typing import Dict, List, Any, Optional


class ReorgPredictor:
    """Предсказание вероятности реорганизации — assessments persisted in SQLite."""

    def __init__(self, db=None):
        self.db = db
        self.history: List[Dict] = []
        self._load_from_db()
        print(f"[Reorg] Predictor initialized ({len(self.history)} assessments, "
              f"persisted={bool(db)})")

    def _load_from_db(self) -> None:
        if not self.db or not hasattr(self.db, "get_reorg_assessments"):
            return
        self.history = self.db.get_reorg_assessments(limit=500)

    def _record(self, kind: str, payload: Dict) -> str:
        assess_id = hashlib.sha256(
            f"{kind}{time.time()}".encode()
        ).hexdigest()[:16]
        entry = {
            "assess_id": assess_id,
            "kind": kind,
            "timestamp": int(time.time()),
            **payload,
        }
        self.history.append(entry)
        if len(self.history) > 2000:
            self.history = self.history[-2000:]
        if self.db and hasattr(self.db, "save_reorg_assessment"):
            self.db.save_reorg_assessment(entry)
        return assess_id

    def calculate_risk(self, confirmations: int, network_stability: float = 1.0) -> float:
        if confirmations <= 0:
            return 0.95
        base_risk = 1.0 / (confirmations + 1)
        risk = base_risk * (1 - network_stability * 0.7)
        risk = min(0.95, max(0.01, risk))
        self._record("risk", {
            "confirmations": confirmations,
            "network_stability": network_stability,
            "risk": risk,
            "confidence": self._confidence_label(risk),
        })
        return risk

    def predict_reorg_depth(self, network_hashrate: float, attacker_hashrate: float) -> int:
        if attacker_hashrate <= 0:
            depth = 0
        else:
            ratio = network_hashrate / attacker_hashrate
            depth = int(math.log(ratio, 2)) if ratio > 1 else 0
        self._record("depth", {
            "network_hashrate": network_hashrate,
            "attacker_hashrate": attacker_hashrate,
            "predicted_depth": depth,
        })
        return depth

    def analyze_fork(self, main_chain: List, fork_chain: List) -> Dict:
        common_ancestor = None
        for i, (main, fork) in enumerate(zip(main_chain, fork_chain)):
            mh = main.get("hash") if isinstance(main, dict) else main
            fh = fork.get("hash") if isinstance(fork, dict) else fork
            if mh == fh:
                common_ancestor = i
            else:
                break
        if common_ancestor is None:
            result = {"error": "No common ancestor found", "fork_detected": True}
            self._record("fork", result)
            return result
        fork_depth = len(fork_chain) - common_ancestor - 1
        main_depth = len(main_chain) - common_ancestor - 1
        is_viable = fork_depth > 0 and fork_depth > main_depth * 0.8
        ancestor_num = -1
        if common_ancestor >= 0 and main_chain:
            m0 = main_chain[common_ancestor]
            ancestor_num = m0.get("number", m0.get("height", common_ancestor)) if isinstance(m0, dict) else common_ancestor
        result = {
            "common_ancestor": ancestor_num,
            "fork_depth": fork_depth,
            "main_depth": main_depth,
            "is_viable": is_viable,
            "fork_detected": fork_depth > 0,
            "risk": self.calculate_risk(max(1, main_depth)),
        }
        self._record("fork", result)
        return result

    def analyze_live_peers(self, local_height: int, peer_heights: List[int]) -> Dict:
        """Live fork risk from P2P height gaps (no chain data required)."""
        if not peer_heights:
            risk = self.calculate_risk(12)
            return {
                "fork_detected": False,
                "local_height": local_height,
                "peer_count": 0,
                "max_peer_gap": 0,
                "risk": risk,
                "confidence": self._confidence_label(risk),
            }
        gaps = [abs(int(local_height) - int(ph)) for ph in peer_heights]
        max_gap = max(gaps) if gaps else 0
        conf = max(1, 12 - max_gap)
        risk = self.calculate_risk(conf)
        result = {
            "fork_detected": max_gap > 1,
            "local_height": local_height,
            "peer_heights": peer_heights,
            "max_peer_gap": max_gap,
            "risk": risk,
            "confidence": self._confidence_label(risk),
        }
        self._record("live_peers", result)
        return result

    def _confidence_label(self, risk: float) -> str:
        if risk < 0.05:
            return "finalized"
        if risk < 0.2:
            return "high"
        if risk < 0.5:
            return "medium"
        return "low"

    def get_confidence(self, confirmations: int) -> str:
        risk = self.calculate_risk(confirmations)
        label = self._confidence_label(risk)
        labels = {
            "finalized": "Finalized",
            "high": "High confidence",
            "medium": "Medium confidence",
            "low": "Low confidence - possible reorg",
        }
        return labels.get(label, label)

    def get_history(self, limit: int = 50) -> List[Dict]:
        return list(reversed(self.history[-limit:]))

    def get_stats(self) -> Dict:
        return {
            "assessments": len(self.history),
            "persisted": bool(self.db),
            "kinds": {
                k: sum(1 for h in self.history if h.get("kind") == k)
                for k in ("risk", "depth", "fork", "live_peers")
            },
        }
