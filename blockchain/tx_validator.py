# blockchain/tx_validator.py
# Полная валидация транзакций

import time
from typing import Dict, Tuple, Optional

SATOSHI_MULTIPLIER = 1_000_000

class TransactionValidator:
    """Полная валидация транзакций перед добавлением в блок"""
    
    # Константы
    MAX_TRANSACTION_SIZE_BYTES = 100 * 1024  # 100 KB
    MIN_TRANSACTION_FEE_SATOSHI = 1000       # 0.001 ABS
    MAX_TRANSACTION_AMOUNT_SATOSHI = 21_000_000 * SATOSHI_MULTIPLIER  # 21M ABS
    
    @classmethod
    def validate(cls, tx: dict, state_manager, mempool=None) -> Tuple[bool, str]:
        """
        Полная валидация транзакции
        Возвращает: (валидна, сообщение_об_ошибке)
        """
        
        # 1. Базовые поля
        if not cls._validate_basic_fields(tx):
            return False, "Missing required fields (from, to, amount)"
        
        from_addr = tx.get('from', tx.get('from_addr', ''))
        to_addr = tx.get('to', tx.get('to_addr', ''))
        
        # 2. Валидация адресов
        if not cls._validate_address(from_addr):
            return False, f"Invalid sender address: {from_addr}"
        if not cls._validate_address(to_addr):
            return False, f"Invalid receiver address: {to_addr}"
        
        # 3. Валидация суммы
        amount_satoshi = tx.get('amount_satoshi', 
                                int(tx.get('amount', 0) * SATOSHI_MULTIPLIER))
        if amount_satoshi <= 0:
            return False, "Amount must be positive"
        if amount_satoshi > cls.MAX_TRANSACTION_AMOUNT_SATOSHI:
            return False, "Amount exceeds maximum"
        
        # 4. Валидация комиссии
        fee_satoshi = tx.get('fee_satoshi',
                             int(tx.get('fee', 0) * SATOSHI_MULTIPLIER))
        if fee_satoshi < cls.MIN_TRANSACTION_FEE_SATOSHI:
            return False, f"Fee too low. Minimum: {cls.MIN_TRANSACTION_FEE_SATOSHI / SATOSHI_MULTIPLIER} ABS"
        
        # 5. Валидация размера
        tx_size = len(str(tx))
        if tx_size > cls.MAX_TRANSACTION_SIZE_BYTES:
            return False, f"Transaction too large: {tx_size} bytes"
        
        # 6. Валидация nonce (защита от replay)
        tx_nonce = tx.get('nonce', 0)
        current_nonce = state_manager.get_account(from_addr).nonce if state_manager.get_account(from_addr) else 0
        if tx_nonce != current_nonce:
            return False, f"Invalid nonce. Expected: {current_nonce}, got: {tx_nonce}"
        
        # 7. Валидация баланса
        balance_satoshi = state_manager.get_balance_satoshi(from_addr)
        total_cost = amount_satoshi + fee_satoshi
        if balance_satoshi < total_cost:
            return False, f"Insufficient balance. Required: {total_cost / SATOSHI_MULTIPLIER} ABS, Available: {balance_satoshi / SATOSHI_MULTIPLIER} ABS"
        
        # 8. Проверка на дубликат в мемпуле
        if mempool and mempool.has_transaction(tx.get('hash', tx.get('tx_hash', ''))):
            return False, "Transaction already in mempool"
        
        # 9. Проверка подписи (если есть)
        if 'signature' in tx and tx['signature']:
            if not cls._verify_signature(tx, tx['signature']):
                return False, "Invalid signature"
        
        return True, "OK"
    
    @classmethod
    def _validate_basic_fields(cls, tx: dict) -> bool:
        required = ['from', 'to', 'amount']
        for field in required:
            if field not in tx and f'{field}_addr' not in tx:
                return False
        return True
    
    @classmethod
    def _validate_address(cls, address: str) -> bool:
        if not address or len(address) < 10:
            return False
        # Базовые проверки
        return True
    
    @classmethod
    def _verify_signature(cls, tx: dict, signature: str) -> bool:
        """Проверка подписи транзакции"""
        # В production: реальная криптография
        return len(signature) >= 64
