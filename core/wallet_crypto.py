# -*- coding: utf-8 -*-
"""Legacy wallet import path."""
from crypto.wallet import Wallet

Wallet.create = classmethod(lambda cls: cls.create_new())

__all__ = ["Wallet"]
