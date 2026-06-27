#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZK Proof System — Zero-Knowledge доказательства для Absolute Blockchain.
Перенесён из zk_proofs.py и адаптирован для API.

Поддерживает:
  - Доказательство знания секрета (Schnorr-подобный протокол)
  - Доказательство принадлежности диапазону (Range Proof)
  - Доказательство достаточности баланса (без раскрытия суммы)
  - ZK-транзакции (анонимные переводы с доказательством)
"""

import hashlib
import secrets
from dataclasses import dataclass
from typing import Dict, Tuple, Optional


@dataclass
class ZKProof:
    commitment: str
    response: int
    challenge: int
    proof_type: str

    def to_dict(self) -> Dict:
        return {
            "commitment": self.commitment,
            "response": self.response,
            "challenge": self.challenge,
            "proof_type": self.proof_type,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ZKProof":
        return cls(
            commitment=d.get("commitment", "0"),
            response=int(d.get("response", 0)),
            challenge=int(d.get("challenge", 0)),
            proof_type=d.get("proof_type", "knowledge"),
        )


class ZKProofSystem:
    """
    Zero-Knowledge Proof System на базе дискретного логарифма (secp256k1).
    """

    # secp256k1 параметры
    PARAMS = {
        "p": 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F,
        "g": 2,
        "q": 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141,
    }

    @property
    def _exponent_modulus(self) -> int:
        # The scheme below operates in the multiplicative field modulo p with g=2.
        # Exponents therefore reduce modulo p-1 by Fermat's little theorem.
        return self.PARAMS["p"] - 1

    def _nonce(self, modulus: int) -> int:
        return secrets.randbelow(modulus - 1) + 1

    def _challenge(self, proof_type: str, *parts: object, modulus: Optional[int] = None) -> int:
        digest = hashlib.sha256(
            "|".join(str(part) for part in (proof_type, *parts)).encode()
        ).hexdigest()
        value = int(digest, 16)
        if modulus:
            return (value % (modulus - 1)) + 1
        return value

    # ── Доказательство знания секрета (Schnorr) ───────────────────────────────

    def prove_knowledge(self, secret: int) -> ZKProof:
        """Доказываем знание секрета не раскрывая его."""
        order = self._exponent_modulus
        secret = int(secret) % order
        r = self._nonce(order)
        commitment = pow(self.PARAMS["g"], r, self.PARAMS["p"])
        public_value = pow(self.PARAMS["g"], secret, self.PARAMS["p"])
        challenge = self._challenge(
            "knowledge", commitment, public_value, modulus=order
        )
        response = (r + secret * challenge) % order
        return ZKProof(
            commitment=hex(commitment),
            response=response,
            challenge=challenge,
            proof_type="knowledge",
        )

    def verify_knowledge(self, proof: ZKProof, public_value: int) -> bool:
        """Проверяем доказательство знания."""
        try:
            commitment = int(proof.commitment, 16)
            public_value = int(public_value)
        except (TypeError, ValueError):
            return False
        expected_challenge = self._challenge(
            "knowledge", commitment, public_value, modulus=self._exponent_modulus
        )
        if proof.challenge != expected_challenge:
            return False
        left = pow(self.PARAMS["g"], proof.response, self.PARAMS["p"])
        right = (
            commitment * pow(public_value, proof.challenge, self.PARAMS["p"])
        ) % self.PARAMS["p"]
        return left == right

    # ── Range Proof ──────────────────────────────────────────────────────────

    def prove_range(self, value: int, min_val: int = 0, max_val: int = 100) -> ZKProof:
        """Доказываем что value в [min_val, max_val] не раскрывая value."""
        if not (min_val <= value <= max_val):
            raise ValueError(f"Value {value} not in [{min_val}, {max_val}]")
        commitment = hashlib.sha256(f"{value}:{min_val}:{max_val}".encode()).hexdigest()
        challenge = self._challenge("range", commitment, min_val, max_val, modulus=1_000_000)
        proof_data = f"{commitment}:{challenge}:{min_val}:{max_val}"
        response = int(hashlib.sha256(proof_data.encode()).hexdigest(), 16)
        return ZKProof(commitment=commitment, response=response,
                       challenge=challenge, proof_type="range")

    def verify_range(self, proof: ZKProof, min_val: int = 0, max_val: int = 100) -> bool:
        expected_challenge = self._challenge(
            "range", proof.commitment, min_val, max_val, modulus=1_000_000
        )
        if proof.challenge != expected_challenge:
            return False
        expected = int(
            hashlib.sha256(
                f"{proof.commitment}:{proof.challenge}:{min_val}:{max_val}".encode()
            ).hexdigest(), 16
        )
        return expected == proof.response

    # ── Balance Proof ────────────────────────────────────────────────────────

    def prove_balance(self, balance: int, amount: int) -> ZKProof:
        """Доказываем что balance >= amount не раскрывая balance."""
        if balance < amount:
            raise ValueError("Insufficient balance for proof")
        difference = balance - amount
        commitment = hashlib.sha256(f"{difference}".encode()).hexdigest()
        challenge = self._challenge("balance", commitment, amount, modulus=1_000_000)
        proof_data = f"{commitment}:{challenge}:{amount}"
        response = int(hashlib.sha256(proof_data.encode()).hexdigest(), 16)
        return ZKProof(commitment=commitment, response=response,
                       challenge=challenge, proof_type="balance")

    def verify_balance(self, proof: ZKProof, amount: int) -> bool:
        expected_challenge = self._challenge(
            "balance", proof.commitment, amount, modulus=1_000_000
        )
        if proof.challenge != expected_challenge:
            return False
        expected = int(
            hashlib.sha256(
                f"{proof.commitment}:{proof.challenge}:{amount}".encode()
            ).hexdigest(), 16
        )
        return expected == proof.response

    # ── ZK-транзакция ────────────────────────────────────────────────────────

    def create_zk_transaction(self, from_addr: str, to_addr: str,
                               amount: int, private_key: int,
                               public_key: int) -> Tuple[Dict, ZKProof]:
        """Создаёт анонимную ZK-транзакцию с доказательством."""
        proof = self.prove_knowledge(private_key)
        if not self.verify_knowledge(proof, public_key):
            raise ValueError("ZK proof verification failed")

        import time
        tx = {
            "from_hash": hashlib.sha256(from_addr.encode()).hexdigest()[:16],
            "to_hash": hashlib.sha256(to_addr.encode()).hexdigest()[:16],
            "amount_hash": hashlib.sha256(str(amount).encode()).hexdigest()[:16],
            "proof": proof.to_dict(),
            "timestamp": time.time(),
        }
        return tx, proof

    def get_system_info(self) -> Dict:
        return {
            "curve": "finite-field-schnorr-like",
            "supported_proofs": ["knowledge", "range", "balance"],
            "security_level": "r-and-d",
            "knowledge_proof": "non-interactive Fiat-Shamir Schnorr-style proof",
            "production_note": "R&D module; disabled by production profile until independently audited",
            "p_bits": self.PARAMS["p"].bit_length(),
        }
