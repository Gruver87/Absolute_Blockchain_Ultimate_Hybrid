# api/handlers/stats_handler.py
from api.utils.response import send_json

def handle_get_stats(handler, data):
    """Получение статистики блокчейна"""
    stats = handler.blockchain.get_blockchain_info()
    send_json(handler, stats)
