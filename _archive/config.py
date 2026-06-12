#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Единая конфигурация блокчейна"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class BlockchainConfig:
    """Основная конфигурация"""
    
    # Версия
    VERSION: str = "57.0"
    NETWORK_NAME: str = "AbsoluteBlockchain"
    
    # Сеть
    API_PORT: int = 8080
    RPC_PORT: int = 8545
    WS_PORT: int = 8546
    P2P_PORT: int = 5000
    
    # Консенсус
    BLOCK_TIME: int = 15
    BLOCK_REWARD: float = 50.0
    TRANSACTION_FEE: float = 0.001
    
    # Стейкинг
    MIN_STAKE: float = 100.0
    STAKING_APY: float = 5.0
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60
    
    # JWT
    JWT_SECRET: str = "absolute_blockchain_secret_key_2024"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Пути
    DATA_DIR: str = "data"
    LOGS_DIR: str = "logs"
    DB_PATH: str = "data/blockchain.db"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'version': self.VERSION,
            'network_name': self.NETWORK_NAME,
            'api_port': self.API_PORT,
            'block_time': self.BLOCK_TIME,
            'block_reward': self.BLOCK_REWARD,
        }

config = BlockchainConfig()

# Создаём директории
os.makedirs(config.DATA_DIR, exist_ok=True)
os.makedirs(config.LOGS_DIR, exist_ok=True)
