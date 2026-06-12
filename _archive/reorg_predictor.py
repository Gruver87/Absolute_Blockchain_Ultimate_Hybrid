#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REORG PREDICTION ENGINE - предсказывает реорганизации цепи"""

import math
from typing import Dict, List, Any

class ReorgPredictor:
    """Предсказание вероятности реорганизации"""
    
    def __init__(self):
        self.history: List[Dict] = []
    
    def calculate_risk(self, confirmations: int, network_stability: float = 1.0) -> float:
        """Расчёт риска реорганизации"""
        if confirmations <= 0:
            return 0.95  # неподтверждённый блок - высокий риск
        
        # Экспоненциальное снижение риска с каждым подтверждением
        base_risk = 1.0 / (confirmations + 1)
        
        # Учитываем стабильность сети (0-1, 1 = идеально)
        risk = base_risk * (1 - network_stability * 0.7)
        
        return min(0.95, max(0.01, risk))
    
    def predict_reorg_depth(self, network_hashrate: float, attacker_hashrate: float) -> int:
        """Предсказание максимальной глубины реорганизации"""
        if attacker_hashrate <= 0:
            return 0
        
        ratio = network_hashrate / attacker_hashrate
        return int(math.log(ratio, 2)) if ratio > 1 else 0
    
    def analyze_fork(self, main_chain: List, fork_chain: List) -> Dict:
        """Анализ форка"""
        common_ancestor = None
        for i, (main, fork) in enumerate(zip(main_chain, fork_chain)):
            if main["hash"] == fork["hash"]:
                common_ancestor = i
                break
        
        if common_ancestor is None:
            return {"error": "No common ancestor found"}
        
        fork_depth = len(fork_chain) - common_ancestor - 1
        main_depth = len(main_chain) - common_ancestor - 1
        
        is_viable = fork_depth > 0 and fork_depth > main_depth * 0.8
        
        return {
            "common_ancestor": main_chain[common_ancestor]["number"] if common_ancestor >= 0 else -1,
            "fork_depth": fork_depth,
            "main_depth": main_depth,
            "is_viable": is_viable,
            "risk": self.calculate_risk(main_depth)
        }
    
    def get_confidence(self, confirmations: int) -> str:
        """Уровень уверенности в блоке"""
        risk = self.calculate_risk(confirmations)
        if risk < 0.05:
            return "✅ Finalized"
        elif risk < 0.2:
            return "🟢 High confidence"
        elif risk < 0.5:
            return "🟡 Medium confidence"
        else:
            return "🔴 Low confidence - possible reorg"

def test_reorg():
    print("🔀 Reorg Prediction Engine")
    print("=" * 40)
    
    predictor = ReorgPredictor()
    
    print("   📊 Risk by confirmations:")
    for conf in [0, 1, 2, 5, 10, 20]:
        risk = predictor.calculate_risk(conf)
        print(f"      Confirmations: {conf} → Risk: {risk*100:.1f}%")
    
    print("\n   🎯 Confidence levels:")
    for conf in [0, 1, 3, 6, 12]:
        print(f"      {conf} confirmations: {predictor.get_confidence(conf)}")
    
    return True

if __name__ == "__main__":
    test_reorg()
