# api/routes/router.py
from api.handlers.wallet_handler import handle_create_wallet
from api.handlers.transaction_handler import handle_send_transaction
from api.handlers.stats_handler import handle_get_stats

# GET роуты
GET_ROUTES = {
    '/api/stats': handle_get_stats,
}

# POST роуты
POST_ROUTES = {
    '/api/wallet/create': handle_create_wallet,
    '/api/transaction/send': handle_send_transaction,
}

def get_handler(path):
    """Получение обработчика для GET запроса"""
    return GET_ROUTES.get(path)

def post_handler(path):
    """Получение обработчика для POST запроса"""
    return POST_ROUTES.get(path)
