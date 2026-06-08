# core/tx_signer.py
# ПОДПИСЬ И ВЕРИФИКАЦИЯ ТРАНЗАКЦИЙ

from typing import Optional
from core.transaction import Transaction
from crypto.wallet import crypto_wallet

class TransactionSigner:
    """Подпись и верификация транзакций с ECDSA"""
    
    @staticmethod
    def sign_transaction(tx: Transaction, private_key_hex: str) -> Optional[Transaction]:
        """Подписание транзакции"""
        try:
            tx.sign(private_key_hex)
            return tx
        except Exception as e:
            print(f"❌ Ошибка подписи: {e}")
            return None
    
    @staticmethod
    def verify_transaction(tx: Transaction) -> bool:
        """Верификация подписи транзакции"""
        if not tx.signature:
            return False
        return tx.verify()
    
    @staticmethod
    def verify_block_transactions(block) -> bool:
        """Верификация всех транзакций в блоке"""
        for tx in block.transactions:
            if not TransactionSigner.verify_transaction(tx):
                print(f"❌ Неверная подпись транзакции {tx.tx_hash[:16]}...")
                return False
        return True

# Тест
if __name__ == "__main__":
    print("=" * 60)
    print("Transaction Signer - Тест")
    print("=" * 60)
    
    from crypto.wallet import crypto_wallet
    
    wallet = crypto_wallet.generate_wallet()
    tx = Transaction.create(
        from_addr=wallet['address'],
        to_addr="receiver",
        amount=100.0,
        private_key=wallet['private_key'],
        public_key=wallet['public_key']
    )
    
    print(f"\n✅ Подпись: {tx.signature[:32]}...")
    print(f"✅ Верификация: {TransactionSigner.verify_transaction(tx)}")
    
    print("\n✅ Transaction Signer готов!")
