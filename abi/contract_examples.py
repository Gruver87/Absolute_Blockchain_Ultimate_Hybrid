# abi/contract_examples.py
"""
Примеры ABI контрактов для тестирования
"""

# Счётчик (increment)
COUNTER_ABI = {
    "increment": [
        ("PUSH", "counter"),
        ("LOAD", None),
        ("PUSH", 1),
        ("ADD", None),
        ("PUSH", "counter"),
        ("STORE", None),
    ],
    "get": [
        ("PUSH", "counter"),
        ("LOAD", None),
    ],
    "reset": [
        ("PUSH", 0),
        ("PUSH", "counter"),
        ("STORE", None),
    ]
}

# Калькулятор
CALCULATOR_ABI = {
    "add": [
        ("PUSH", "result"),
        ("LOAD", None),
        ("PUSH", "arg"),
        ("LOAD", None),
        ("ADD", None),
        ("PUSH", "result"),
        ("STORE", None),
    ],
    "get_result": [
        ("PUSH", "result"),
        ("LOAD", None),
    ]
}

# Простой холдер (держатель значения)
VALUE_HOLDER_ABI = {
    "set": [
        ("PUSH", "value"),
        ("STORE", None),
    ],
    "get": [
        ("PUSH", "value"),
        ("LOAD", None),
    ]
}

# Все ABI в одном месте
ALL_ABIS = {
    "counter": COUNTER_ABI,
    "calculator": CALCULATOR_ABI,
    "holder": VALUE_HOLDER_ABI
}

def get_abi(name: str) -> dict:
    """Получить ABI по имени"""
    return ALL_ABIS.get(name, {})
