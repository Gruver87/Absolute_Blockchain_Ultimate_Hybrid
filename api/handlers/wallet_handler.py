# api/handlers/wallet_handler.py
import time
from api.utils.response import send_json, send_error

def handle_create_wallet(handler, data):
    """Создание кошелька"""
    try:
        wallet = handler.quantum_crypto.generate_quantum_keypair()
        
        # БЕЗОПАСНО: НЕ возвращаем приватный ключ!
        response = {
            'success': True,
            'address': wallet.get('quantum_address', wallet.get('address')),
            'public_key': wallet.get('public_key'),
            'algorithm': wallet.get('algorithm', 'SPHINCS+'),
            'created_at': int(time.time())
        }
        send_json(handler, response)
    except Exception as e:
        send_error(handler, str(e), 500)
