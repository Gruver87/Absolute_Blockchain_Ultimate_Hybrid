# p2p/wire.py
# БИНАРНЫЙ СЕТЕВОЙ ПРОТОКОЛ - msgpack

import msgpack
import hashlib
import json
from typing import Dict, Any

class Wire:
    """Бинарный протокол обмена сообщениями"""
    
    @staticmethod
    def pack(msg: Dict) -> bytes:
        """Упаковка сообщения в бинарный формат"""
        return msgpack.packb(msg, use_bin_type=True)
    
    @staticmethod
    def unpack(data: bytes) -> Dict:
        """Распаковка бинарного сообщения"""
        return msgpack.unpackb(data, raw=False)
    
    @staticmethod
    def hash_message(msg: Dict) -> str:
        """Хеш сообщения для инвентаризации"""
        return hashlib.sha256(Wire.pack(msg)).hexdigest()

# Типы сообщений
MSG_INV = "inv"           # "у меня есть блок/tx"
MSG_GETDATA = "getdata"   # "дай блок"
MSG_BLOCK = "block"       # "вот блок"
MSG_HEADERS = "headers"   # "дай заголовки"
MSG_TX = "tx"             # "новая транзакция"
MSG_PING = "ping"         # "проверка соединения"
MSG_PONG = "pong"         # "ответ на ping"
MSG_GETHEADERS = "getheaders"  # "запрос заголовков"

# Роли узлов
NODE_FULL = "full"
NODE_LIGHT = "light"
NODE_VALIDATOR = "validator"

# Тест
if __name__ == "__main__":
    test_msg = {"type": MSG_PING, "data": "hello"}
    packed = Wire.pack(test_msg)
    unpacked = Wire.unpack(packed)
    print(f"✅ Wire протокол работает: {unpacked}")
