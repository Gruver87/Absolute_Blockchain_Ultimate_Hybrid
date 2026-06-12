#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Absolute Blockchain — единая конфигурация узла.
Все параметры системы берутся отсюда.
"""

import json
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    # ── Идентификация сети ──────────────────────────────────────────────────
    chain_id: int = 1337
    network_name: str = "Absolute"
    node_version: str = "1.0.0"

    # ── Монета (токеномика D.U.P. / Uladzimir Dabranski) ───────────────────
    coin_symbol: str = "ABS"
    coin_name: str = "Absolute"
    max_supply: int = 221_000_000       # жёсткий лимит: 221 млн ABS
    genesis_supply: int = 110_500_000   # genesis-эмиссия (без mining pool)
    founder_percent: float = 17.4       # доля основателя D.U.P.
    founder_amount: float = 38_454_000  # 17.4% от 221M
    founder_address: str = ""           # заполняется из wallet при запуске
    founder_initials: str = "D.U.P."
    founder_name: str = "Uladzimir Dabranski"
    block_reward: float = 50.0          # вознаграждение майнера за блок (из mining pool)
    burn_rate: float = 0.02             # 2% каждой комиссии сжигается навсегда
    burn_address: str = "0x000000000000000000000000000000000000dead"
    base_gas_price: int = 21_000        # базовая стоимость перевода в gas units
    gas_price_wei: float = 0.000_000_1  # цена одного gas в ABS

    # ── Сервера ─────────────────────────────────────────────────────────────
    rpc_host: str = "0.0.0.0"
    rpc_port: int = 8545        # JSON-RPC (Ethereum-совместимый)
    http_host: str = "0.0.0.0"
    http_port: int = 8080       # REST API
    ws_port: int = 8766         # WebSocket
    p2p_host: str = "0.0.0.0"
    p2p_port: int = 5000        # P2P сеть

    # ── База данных ─────────────────────────────────────────────────────────
    db_path: str = "data/blockchain.db"
    db_wal_mode: bool = True            # WAL для производительности SQLite

    # ── Майнинг / Консенсус ─────────────────────────────────────────────────
    block_time: int = 15                # секунд между блоками
    epoch_size: int = 32                # блоков в эпохе (staking release)
    max_tx_per_block: int = 500
    mining_enabled: bool = True
    miner_address: str = ""             # заполняется из wallet при запуске
    validator_count: int = 21
    min_stake: float = 1000.0           # минимальный стейк валидатора

    # ── P2P ─────────────────────────────────────────────────────────────────
    bootstrap_peers: List[str] = field(default_factory=list)
    max_peers: int = 50
    peer_timeout: int = 30              # секунд до отключения неактивного пира
    sync_batch_size: int = 100          # блоков за один запрос синхронизации

    # ── EVM ─────────────────────────────────────────────────────────────────
    evm_enabled: bool = True
    evm_gas_limit: int = 8_000_000

    # ── Мост (Cross-chain bridge) ────────────────────────────────────────────
    bridge_enabled: bool = True
    bridge_mode: str = "simulator"      # "simulator" | "rust"
    rust_bridge_path: str = "bridge/abs_bridge_bin"

    # ── Логирование ─────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "data/node.log"

    # ────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_json(cls, path: str) -> "Config":
        """Загрузить конфигурацию из JSON-файла."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = cls()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg

    def to_json(self, path: str) -> None:
        """Сохранить конфигурацию в JSON-файл."""
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
        data = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def base_fee(self) -> float:
        """Базовая комиссия за обычный перевод в ABS."""
        return self.base_gas_price * self.gas_price_wei

    def __repr__(self) -> str:
        return (
            f"Config(chain={self.chain_id} '{self.network_name}', "
            f"rpc=:{self.rpc_port}, http=:{self.http_port}, "
            f"p2p=:{self.p2p_port}, db='{self.db_path}')"
        )
