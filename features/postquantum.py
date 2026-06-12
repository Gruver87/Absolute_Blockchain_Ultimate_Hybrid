#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔐 ЧАСТЬ 28: POST-QUANTUM CRYPTO - ЯДРО
🔐 WATERMARK: DABRANSKI ULADZIMIR PETROVICH | 14.07.1987 | GRODNO

Квантово-устойчивые криптографические алгоритмы
SPHINCS+, Kyber, Dilithium, Falcon
"""

import hashlib
import time
import json
import secrets
import math
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import numpy as np


# ============================================================================
# ТИПЫ АЛГОРИТМОВ
# ============================================================================

class PQAlgorithm(Enum):
    """Типы пост-квантовых алгоритмов"""
    SPHINCS_PLUS = "sphincs_plus"      # Хеш-подписи (статические)
    KYBER = "kyber"                     # KEM на основе решёток
    DILITHIUM = "dilithium"             # Цифровые подписи на решётках
    FALCON = "falcon"                   # Компактные подписи на решётках
    CLASSIC_MCELIECE = "classic_mceliece" # Коды Гоппы


class SecurityLevel(Enum):
    """Уровни безопасности (NIST)"""
    LEVEL1 = 1   # 128 бит (AES-128)
    LEVEL3 = 3   # 192 бита (AES-192)
    LEVEL5 = 5   # 256 бит (AES-256)


# ============================================================================
# ДАТАКЛАССЫ
# ============================================================================

@dataclass
class PQKeyPair:
    """Пост-квантовая ключевая пара"""
    
    algorithm: PQAlgorithm
    security_level: SecurityLevel
    public_key: bytes
    private_key: bytes
    created_at: float = field(default_factory=time.time)
    key_id: str = ""
    
    def __post_init__(self):
        if not self.key_id:
            self.key_id = hashlib.sha256(
                f"{self.algorithm.value}{time.time()}{secrets.token_hex(8)}".encode()
            ).hexdigest()[:16]
    
    def to_dict(self) -> Dict:
        return {
            'id': self.key_id[:8],
            'algorithm': self.algorithm.value,
            'security': f"NIST{self.security_level.value}",
            'public_key_size': len(self.public_key),
            'private_key_size': len(self.private_key),
            'created': self.created_at
        }


@dataclass
class PQSignature:
    """Пост-квантовая подпись"""
    
    id: str
    algorithm: PQAlgorithm
    signature: bytes
    public_key_hash: str
    message_hash: str
    timestamp: float = field(default_factory=time.time)
    verified: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id[:8],
            'algorithm': self.algorithm.value,
            'size': len(self.signature),
            'verified': self.verified
        }


@dataclass
class SharedSecret:
    """Общий секрет (для KEM)"""
    
    id: str
    algorithm: PQAlgorithm
    ciphertext: bytes
    shared_secret: bytes
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id[:8],
            'algorithm': self.algorithm.value,
            'ciphertext_size': len(self.ciphertext),
            'secret_size': len(self.shared_secret)
        }


# ============================================================================
# SPHINCS+ (ХЕШ-ПОДПИСИ)
# ============================================================================

class SPHINCSPlus:
    """
    SPHINCS+ - статическая хеш-подпись
    Безопасна против квантовых компьютеров
    """
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.LEVEL5):
        self.security_level = security_level
        
        # Параметры в зависимости от уровня безопасности
        self.params = {
            SecurityLevel.LEVEL1: {
                'n': 16,  # байт
                'h': 64,  # высота дерева
                'd': 8,   # слои
                'k': 14,  # виног
                'w': 16,  # Winternitz
                'key_size': 32,
                'sig_size': 8080
            },
            SecurityLevel.LEVEL3: {
                'n': 24,
                'h': 64,
                'd': 8,
                'k': 22,
                'w': 16,
                'key_size': 48,
                'sig_size': 17000
            },
            SecurityLevel.LEVEL5: {
                'n': 32,
                'h': 64,
                'd': 8,
                'k': 30,
                'w': 16,
                'key_size': 64,
                'sig_size': 30000
            }
        }
        
    def generate_keypair(self) -> PQKeyPair:
        """Генерация ключевой пары"""
        
        params = self.params[self.security_level]
        
        # Симуляция генерации ключей
        # В реальности сложный процесс построения дерева Меркла
        
        seed = secrets.token_bytes(params['key_size'])
        
        # Публичный ключ = корень дерева + seed
        public_key = hashlib.sha3_512(seed).digest()[:params['key_size'] * 2]
        private_key = seed + secrets.token_bytes(params['key_size'] * 4)
        
        return PQKeyPair(
            algorithm=PQAlgorithm.SPHINCS_PLUS,
            security_level=self.security_level,
            public_key=public_key,
            private_key=private_key
        )
    
    def sign(self, message: bytes, keypair: PQKeyPair) -> PQSignature:
        """Подписание сообщения"""
        
        message_hash = hashlib.sha3_512(message).hexdigest()
        
        # Симуляция подписи
        signature_data = hashlib.sha3_512(
            message_hash.encode() + keypair.private_key + secrets.token_bytes(32)
        ).digest()
        
        # Увеличиваем размер до реального SPHINCS+
        signature = signature_data * (self.params[self.security_level]['sig_size'] // 64)
        
        return PQSignature(
            id=hashlib.sha256(f"{message_hash}{time.time()}".encode()).hexdigest()[:16],
            algorithm=PQAlgorithm.SPHINCS_PLUS,
            signature=signature[:self.params[self.security_level]['sig_size']],
            public_key_hash=hashlib.sha256(keypair.public_key).hexdigest(),
            message_hash=message_hash
        )
    
    def verify(self, signature: PQSignature, message: bytes, public_key: bytes) -> bool:
        """Проверка подписи"""
        
        # Симуляция проверки
        expected_hash = hashlib.sha3_512(message).hexdigest()
        
        if expected_hash != signature.message_hash:
            return False
        
        # Симуляция успешной проверки
        signature.verified = True
        return True


# ============================================================================
# KYBER (KEM - KEY ENCAPSULATION MECHANISM)
# ============================================================================

class Kyber:
    """
    Kyber - KEM на основе решёток (ML-KEM)
    Для обмена ключами
    """
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.LEVEL5):
        self.security_level = security_level
        
        self.params = {
            SecurityLevel.LEVEL1: {
                'k': 2,   # ранг матрицы
                'eta1': 3,
                'eta2': 2,
                'du': 10,
                'dv': 4,
                'key_size': 800,
                'ct_size': 768
            },
            SecurityLevel.LEVEL3: {
                'k': 3,
                'eta1': 2,
                'eta2': 2,
                'du': 10,
                'dv': 4,
                'key_size': 1184,
                'ct_size': 1088
            },
            SecurityLevel.LEVEL5: {
                'k': 4,
                'eta1': 2,
                'eta2': 2,
                'du': 11,
                'dv': 5,
                'key_size': 1568,
                'ct_size': 1568
            }
        }
        
    def generate_keypair(self) -> PQKeyPair:
        """Генерация ключевой пары для KEM"""
        
        params = self.params[self.security_level]
        
        # Симуляция матрицы A ∈ R_q^{k×k}
        seed_a = secrets.token_bytes(32)
        
        # Случайная матрица S (секретный ключ)
        private_key = secrets.token_bytes(params['key_size'] // 2)
        
        # Публичный ключ = (A, t = A*s + e)
        public_key = hashlib.sha3_512(seed_a + private_key).digest()[:params['key_size']]
        
        return PQKeyPair(
            algorithm=PQAlgorithm.KYBER,
            security_level=self.security_level,
            public_key=public_key,
            private_key=private_key
        )
    
    def encapsulate(self, public_key: bytes) -> SharedSecret:
        """Создание общего секрета (для отправителя)"""
        
        params = self.params[self.security_level]
        
        # Генерируем случайный секрет
        secret = secrets.token_bytes(32)
        
        # Шифруем секрет публичным ключом
        ciphertext = hashlib.sha3_512(public_key + secret).digest()[:params['ct_size']]
        
        return SharedSecret(
            id=hashlib.sha256(f"{time.time()}{secrets.token_hex(4)}".encode()).hexdigest()[:16],
            algorithm=PQAlgorithm.KYBER,
            ciphertext=ciphertext,
            shared_secret=secret
        )
    
    def decapsulate(self, ciphertext: bytes, keypair: PQKeyPair) -> Optional[SharedSecret]:
        """Извлечение общего секрета (для получателя)"""
        
        params = self.params[self.security_level]
        
        # Расшифровываем секрет
        # В реальности сложная операция с решётками
        
        # Симуляция успешной расшифровки
        secret = hashlib.sha3_512(ciphertext + keypair.private_key).digest()[:32]
        
        return SharedSecret(
            id=hashlib.sha256(f"{time.time()}{secrets.token_hex(4)}".encode()).hexdigest()[:16],
            algorithm=PQAlgorithm.KYBER,
            ciphertext=ciphertext,
            shared_secret=secret
        )


# ============================================================================
# DILITHIUM (ПОДПИСИ НА РЕШЁТКАХ)
# ============================================================================

class Dilithium:
    """
    Dilithium - цифровые подписи на решётках (ML-DSA)
    NIST стандарт для пост-квантовых подписей
    """
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.LEVEL5):
        self.security_level = security_level
        
        self.params = {
            SecurityLevel.LEVEL1: {
                'k': 4,
                'l': 4,
                'eta': 2,
                'tau': 39,
                'gamma1': 131072,
                'gamma2': 95232,
                'key_size': 1312,
                'sig_size': 2420
            },
            SecurityLevel.LEVEL3: {
                'k': 6,
                'l': 5,
                'eta': 4,
                'tau': 49,
                'gamma1': 131072,
                'gamma2': 261888,
                'key_size': 1952,
                'sig_size': 3293
            },
            SecurityLevel.LEVEL5: {
                'k': 8,
                'l': 7,
                'eta': 2,
                'tau': 60,
                'gamma1': 131072,
                'gamma2': 261888,
                'key_size': 2592,
                'sig_size': 4595
            }
        }
        
    def generate_keypair(self) -> PQKeyPair:
        """Генерация ключевой пары"""
        
        params = self.params[self.security_level]
        
        # Генерация seed
        seed = secrets.token_bytes(32)
        
        # В реальности: A ∈ R_q^{k×l}, s1, s2
        public_key = hashlib.shake_256(seed).digest(params['key_size'])
        private_key = seed + secrets.token_bytes(params['key_size'])
        
        return PQKeyPair(
            algorithm=PQAlgorithm.DILITHIUM,
            security_level=self.security_level,
            public_key=public_key,
            private_key=private_key
        )
    
    def sign(self, message: bytes, keypair: PQKeyPair) -> PQSignature:
        """Подписание сообщения"""
        
        params = self.params[self.security_level]
        message_hash = hashlib.sha3_512(message).hexdigest()
        
        # Симуляция подписи (в реальности: z = y + cs1)
        signature = hashlib.shake_256(
            message_hash.encode() + keypair.private_key
        ).digest(params['sig_size'])
        
        return PQSignature(
            id=hashlib.sha256(f"{message_hash}{time.time()}".encode()).hexdigest()[:16],
            algorithm=PQAlgorithm.DILITHIUM,
            signature=signature,
            public_key_hash=hashlib.sha256(keypair.public_key).hexdigest(),
            message_hash=message_hash
        )
    
    def verify(self, signature: PQSignature, message: bytes, public_key: bytes) -> bool:
        """Проверка подписи"""
        
        expected_hash = hashlib.sha3_512(message).hexdigest()
        
        if expected_hash != signature.message_hash:
            return False
        
        # Симуляция проверки нормы
        signature.verified = True
        return True


# ============================================================================
# FALCON (КОМПАКТНЫЕ ПОДПИСИ)
# ============================================================================

class Falcon:
    """
    FALCON - компактные пост-квантовые подписи
    Основаны на решётках NTRU
    """
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.LEVEL5):
        self.security_level = security_level
        
        self.params = {
            SecurityLevel.LEVEL1: {
                'n': 512,
                'key_size': 897,
                'sig_size': 666,
                'logn': 9
            },
            SecurityLevel.LEVEL3: {
                'n': 768,
                'key_size': 1233,
                'sig_size': 986,
                'logn': 10
            },
            SecurityLevel.LEVEL5: {
                'n': 1024,
                'key_size': 1569,
                'sig_size': 1280,
                'logn': 10
            }
        }
        
    def generate_keypair(self) -> PQKeyPair:
        """Генерация ключевой пары"""
        
        params = self.params[self.security_level]
        
        # Генерация полиномов f, g, F, G из NTRU
        seed = secrets.token_bytes(32)
        
        public_key = hashlib.shake_256(seed).digest(params['key_size'] // 2)
        private_key = seed + secrets.token_bytes(params['key_size'])
        
        return PQKeyPair(
            algorithm=PQAlgorithm.FALCON,
            security_level=self.security_level,
            public_key=public_key,
            private_key=private_key
        )
    
    def sign(self, message: bytes, keypair: PQKeyPair) -> PQSignature:
        """Подписание сообщения (Fast Fourier sampling)"""
        
        params = self.params[self.security_level]
        message_hash = hashlib.sha3_512(message).hexdigest()
        
        # Симуляция подписи с компактным представлением
        signature = hashlib.shake_256(
            message_hash.encode() + keypair.private_key
        ).digest(params['sig_size'])
        
        return PQSignature(
            id=hashlib.sha256(f"{message_hash}{time.time()}".encode()).hexdigest()[:16],
            algorithm=PQAlgorithm.FALCON,
            signature=signature,
            public_key_hash=hashlib.sha256(keypair.public_key).hexdigest(),
            message_hash=message_hash
        )
    
    def verify(self, signature: PQSignature, message: bytes, public_key: bytes) -> bool:
        """Проверка подписи"""
        
        expected_hash = hashlib.sha3_512(message).hexdigest()
        
        if expected_hash != signature.message_hash:
            return False
        
        signature.verified = True
        return True


# ============================================================================
# МЕНЕДЖЕР ПОСТ-КВАНТОВОЙ КРИПТОГРАФИИ
# ============================================================================

class PostQuantumManager:
    """
    Менеджер пост-квантовой криптографии
    Объединяет все алгоритмы
    """
    
    def __init__(self):
        self.algorithms = {
            PQAlgorithm.SPHINCS_PLUS: SPHINCSPlus(),
            PQAlgorithm.KYBER: Kyber(),
            PQAlgorithm.DILITHIUM: Dilithium(),
            PQAlgorithm.FALCON: Falcon()
        }
        self.keypairs: Dict[str, PQKeyPair] = {}
        self.signatures: Dict[str, PQSignature] = {}
        self.secrets: Dict[str, SharedSecret] = {}
        
    def generate_keypair(
        self,
        algorithm: PQAlgorithm,
        security_level: SecurityLevel = SecurityLevel.LEVEL5
    ) -> PQKeyPair:
        """Генерация ключевой пары"""
        
        algo = self.algorithms.get(algorithm)
        if not algo:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        keypair = algo.generate_keypair()
        self.keypairs[keypair.key_id] = keypair
        
        return keypair
    
    def sign(
        self,
        message: bytes,
        keypair: PQKeyPair,
        algorithm: Optional[PQAlgorithm] = None
    ) -> PQSignature:
        """Подписание сообщения"""
        
        if algorithm is None:
            algorithm = keypair.algorithm
        
        algo = self.algorithms.get(algorithm)
        if not algo:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
        
        signature = algo.sign(message, keypair)
        self.signatures[signature.id] = signature
        
        return signature
    
    def verify(
        self,
        signature: PQSignature,
        message: bytes,
        public_key: bytes
    ) -> bool:
        """Проверка подписи"""
        
        algo = self.algorithms.get(signature.algorithm)
        if not algo:
            return False
        
        return algo.verify(signature, message, public_key)
    
    def encapsulate(self, algorithm: PQAlgorithm, public_key: bytes) -> SharedSecret:
        """Создание общего секрета"""
        
        algo = self.algorithms.get(algorithm)
        if not algo:
            raise ValueError(f"Unsupported algorithm for KEM: {algorithm}")
        
        if not hasattr(algo, 'encapsulate'):
            raise ValueError(f"{algorithm} does not support KEM")
        
        secret = algo.encapsulate(public_key)
        self.secrets[secret.id] = secret
        
        return secret
    
    def decapsulate(
        self,
        ciphertext: bytes,
        keypair: PQKeyPair
    ) -> Optional[SharedSecret]:
        """Извлечение общего секрета"""
        
        algo = self.algorithms.get(keypair.algorithm)
        if not algo or not hasattr(algo, 'decapsulate'):
            return None
        
        secret = algo.decapsulate(ciphertext, keypair)
        if secret:
            self.secrets[secret.id] = secret
        
        return secret
    
    def get_keypair(self, key_id: str) -> Optional[PQKeyPair]:
        """Получение ключевой пары по ID"""
        return self.keypairs.get(key_id)
    
    def get_signature(self, sig_id: str) -> Optional[PQSignature]:
        """Получение подписи по ID"""
        return self.signatures.get(sig_id)
    
    def get_stats(self) -> Dict:
        """Статистика пост-квантовой криптографии"""
        
        return {
            'keypairs': len(self.keypairs),
            'signatures': len(self.signatures),
            'secrets': len(self.secrets),
            'by_algorithm': {
                algo.value: len([k for k in self.keypairs.values() if k.algorithm == algo])
                for algo in PQAlgorithm
            }
        }


# ============================================================================
# ГИБРИДНАЯ КРИПТОГРАФИЯ (КЛАССИЧЕСКАЯ + ПОСТ-КВАНТОВАЯ)
# ============================================================================

class HybridCrypto:
    """
    Гибридная криптография
    Комбинирует классические и пост-квантовые алгоритмы
    """
    
    def __init__(self, pq_manager: PostQuantumManager):
        self.pq = pq_manager
        
    def hybrid_sign(self, message: bytes, pq_keypair: PQKeyPair, ecdsa_key: str) -> Dict:
        """
        Гибридная подпись (ECDSA + пост-квант)
        """
        # Пост-квантовая подпись
        pq_sig = self.pq.sign(message, pq_keypair)
        
        # ECDSA подпись (упрощённо)
        ecdsa_sig = hashlib.sha256(message + ecdsa_key.encode()).hexdigest()
        
        return {
            'pq_signature': pq_sig.to_dict(),
            'ecdsa_signature': ecdsa_sig,
            'timestamp': time.time()
        }
    
    def hybrid_encrypt(self, message: bytes, pq_public_key: bytes, ecdsa_public_key: str) -> Dict:
        """
        Гибридное шифрование
        """
        # Создаём общий секрет через Kyber
        kem = self.pq.encapsulate(PQAlgorithm.KYBER, pq_public_key)
        
        # Используем общий секрет для AES шифрования
        aes_key = kem.shared_secret[:32]
        
        # Симуляция AES-GCM
        ciphertext = hashlib.shake_256(message + aes_key).digest(len(message) + 16)
        
        return {
            'kem_ciphertext': kem.ciphertext.hex(),
            'aes_ciphertext': ciphertext.hex(),
            'ecdsa_public': ecdsa_public_key
        }
    
    def hybrid_decrypt(self, encrypted: Dict, pq_keypair: PQKeyPair) -> Optional[bytes]:
        """
        Гибридное расшифрование
        """
        # Извлекаем общий секрет
        kem_cipher = bytes.fromhex(encrypted['kem_ciphertext'])
        secret = self.pq.decapsulate(kem_cipher, pq_keypair)
        
        if not secret:
            return None
        
        # Расшифровываем AES
        aes_key = secret.shared_secret[:32]
        ciphertext = bytes.fromhex(encrypted['aes_ciphertext'])
        
        # Симуляция расшифровки
        plaintext = hashlib.shake_256(ciphertext + aes_key).digest(len(ciphertext) - 16)
        
        return plaintext