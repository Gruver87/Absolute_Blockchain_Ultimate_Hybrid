#!/usr/bin/env python3
"""ZK-PROOF TOY SYSTEM - упрощённые доказательства с нулевым разглашением"""

import hashlib
import random
from typing import Dict, Any

class ZKProofSystem:
    """Учебная реализация ZK-доказательств"""
    
    def __init__(self):
        self.proofs: Dict[str, Dict] = {}
    
    def prove_balance(self, address: str, balance: int, claimed: int) -> Dict:
        """Доказательство, что баланс >= claimed без раскрытия точного значения"""
        
        # Симуляция доказательства
        proof_hash = hashlib.sha256(f"{address}{balance}{claimed}{random.random()}".encode()).hexdigest()[:16]
        
        valid = balance >= claimed
        
        self.proofs[proof_hash] = {
            "address": address,
            "claimed": claimed,
            "valid": valid,
            "timestamp": __import__("time").time()
        }
        
        return {
            "proof": proof_hash,
            "valid": valid,
            "message": f"Proof that balance >= {claimed}"
        }
    
    def verify_proof(self, proof_hash: str) -> Dict:
        if proof_hash in self.proofs:
            proof = self.proofs[proof_hash]
            return {
                "verified": proof["valid"],
                "claimed": proof["claimed"],
                "message": "Proof verified successfully" if proof["valid"] else "Proof invalid"
            }
        return {"verified": False, "message": "Proof not found"}
    
    def get_stats(self) -> Dict:
        return {
            "total_proofs": len(self.proofs),
            "valid_proofs": sum(1 for p in self.proofs.values() if p["valid"])
        }

def test_zk():
    print("🔐 ZK-Proof System Test")
    print("=" * 40)
    
    zk = ZKProofSystem()
    
    # Создаём доказательство
    result = zk.prove_balance("0xuser", 1000, 500)
    print(f"   🔑 Proof generated: {result['proof'][:16]}...")
    print(f"   ✅ Valid: {result['valid']}")
    
    # Верифицируем
    verify = zk.verify_proof(result["proof"])
    print(f"   🔒 Verification: {verify['verified']}")
    
    stats = zk.get_stats()
    print(f"   📊 Total proofs: {stats['total_proofs']}")
    
    return True

if __name__ == "__main__":
    test_zk()
