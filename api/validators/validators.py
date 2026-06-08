"""
Валидаторы для входных данных
"""

import re

ADDRESS_REGEX = re.compile(r'^[a-zA-Z0-9]{32,128}$')

def validate_address(address: str) -> bool:
    if not address:
        return False
    return bool(ADDRESS_REGEX.match(address))

def validate_amount(amount) -> bool:
    try:
        amount = float(amount)
        return amount > 0
    except:
        return False

def validate_positive_int(value) -> bool:
    try:
        return int(value) > 0
    except:
        return False
