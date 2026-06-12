# blockchain/tx_validator.py
# Полная валидация транзакций

import time
from typing import Dict, Tuple, Optional

SATOSHI_MULTIPLIER = 1_000_000


class TransactionValidator:
    """Полная валидация транзакций перед добавлением в блок или мемпул."""

    MAX_TRANSACTION_SIZE_BYTES = 100 * 1024
    MIN_TRANSACTION_FEE_SATOSHI = 1000
    MAX_TRANSACTION_AMOUNT_SATOSHI = 21_000_000 * SATOSHI_MULTIPLIER

    @classmethod
    def validate(
        cls,
        tx: dict,
        state_manager,
        mempool=None,
        chain_id: int = 1,
        require_signature: bool = False,
    ) -> Tuple[bool, str]:
        if not cls._validate_basic_fields(tx):
            return False, "Missing required fields (from, to, amount)"

        from_addr = tx.get("from", tx.get("from_addr", ""))
        to_addr = tx.get("to", tx.get("to_addr", ""))

        if not cls._validate_address(from_addr):
            return False, f"Invalid sender address: {from_addr}"
        if not cls._validate_address(to_addr):
            return False, f"Invalid receiver address: {to_addr}"

        amount_satoshi = tx.get(
            "amount_satoshi", int(float(tx.get("amount", tx.get("value", 0))) * SATOSHI_MULTIPLIER)
        )
        if amount_satoshi <= 0:
            return False, "Amount must be positive"
        if amount_satoshi > cls.MAX_TRANSACTION_AMOUNT_SATOSHI:
            return False, "Amount exceeds maximum"

        fee_satoshi = tx.get("fee_satoshi", int(float(tx.get("fee", 0)) * SATOSHI_MULTIPLIER))
        if fee_satoshi < cls.MIN_TRANSACTION_FEE_SATOSHI:
            return False, (
                f"Fee too low. Minimum: {cls.MIN_TRANSACTION_FEE_SATOSHI / SATOSHI_MULTIPLIER} ABS"
            )

        if len(str(tx)) > cls.MAX_TRANSACTION_SIZE_BYTES:
            return False, "Transaction too large"

        account = state_manager.get_account(from_addr)
        current_nonce = account.nonce if account else 0
        tx_nonce = int(tx.get("nonce", 0))
        if tx_nonce != current_nonce:
            return False, f"Invalid nonce. Expected: {current_nonce}, got: {tx_nonce}"

        balance_satoshi = state_manager.get_balance_satoshi(from_addr)
        total_cost = amount_satoshi + fee_satoshi
        if balance_satoshi < total_cost:
            return False, (
                f"Insufficient balance. Required: {total_cost / SATOSHI_MULTIPLIER} ABS, "
                f"Available: {balance_satoshi / SATOSHI_MULTIPLIER} ABS"
            )

        tx_hash = tx.get("hash", tx.get("tx_hash", ""))
        if mempool and tx_hash and mempool.has_transaction(tx_hash):
            return False, "Transaction already in mempool"

        signature = tx.get("signature", "")
        public_key = tx.get("public_key", "")
        if require_signature and not signature:
            return False, "Signature required"
        if signature:
            if not public_key:
                return False, "public_key required with signature"
            if not cls._verify_signature(tx, signature, chain_id):
                return False, "Invalid signature"

        return True, "OK"

    @classmethod
    def _validate_basic_fields(cls, tx: dict) -> bool:
        has_from = "from" in tx or "from_addr" in tx
        has_to = "to" in tx or "to_addr" in tx
        has_amount = "amount" in tx or "value" in tx or "amount_satoshi" in tx
        return has_from and has_to and has_amount

    @classmethod
    def _validate_address(cls, address: str) -> bool:
        if not address or len(address) < 10:
            return False
        if address.startswith("0x") and len(address) != 42:
            return False
        return True

    @classmethod
    def _verify_signature(cls, tx: dict, signature: str, chain_id: int) -> bool:
        try:
            from crypto.wallet import verify_transaction_signature
            tx_dict = {
                "from": tx.get("from", tx.get("from_addr", "")),
                "to": tx.get("to", tx.get("to_addr", "")),
                "value": int(tx.get("value", tx.get("amount", 0))),
                "nonce": int(tx.get("nonce", 0)),
                "chain_id": chain_id,
                "signature": signature,
                "public_key": tx.get("public_key", ""),
            }
            return verify_transaction_signature(tx_dict)
        except Exception:
            return False
