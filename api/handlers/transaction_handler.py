# api/handlers/transaction_handler.py
import time
import hashlib
from api.utils.response import send_json, send_error
from api.validators.validators import validate_address, validate_amount

def handle_send_transaction(handler, data):
    """Отправка транзакции"""
    from_addr = data.get('from')
    to_addr = data.get('to')
    
    try:
        amount = float(data.get('amount', 0))
    except:
        send_error(handler, 'Invalid amount', 400)
        return
    
    if amount <= 0:
        send_error(handler, 'Amount must be positive', 400)
        return
    
    if not validate_address(from_addr):
        send_error(handler, 'Invalid sender address', 400)
        return
    
    if not validate_address(to_addr):
        send_error(handler, 'Invalid receiver address', 400)
        return
    
    # Создаём транзакцию
    tx_hash = hashlib.sha256(
        f"{from_addr}{to_addr}{amount}{time.time()}".encode()
    ).hexdigest()
    
    from models.transaction import Transaction
    tx = Transaction(
        hash=tx_hash,
        from_addr=from_addr,
        to_addr=to_addr,
        amount=amount,
        fee=handler.config.economic.TRANSACTION_FEE,
        signature='',
        timestamp=int(time.time())
    )
    
    success = handler.blockchain.add_transaction(tx)
    
    send_json(handler, {
        'success': success,
        'tx_hash': tx_hash if success else None,
        'amount': amount,
        'fee': handler.config.economic.TRANSACTION_FEE
    })
