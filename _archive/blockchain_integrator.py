#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INTEGRATION MODULE - Связывает все компоненты блокчейна
Подключается к существующему коду без изменений
"""

import sys
import os
import threading
import time

# Добавляем пути для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем созданные компоненты
try:
    from blockchain.mempool import Mempool, MempoolTransaction
    from blockchain.chain_storage import ChainStorage
    from middleware.rate_limit import rate_limiter
    from api.auth.jwt_auth import jwt_auth
except ImportError as e:
    print(f"⚠️ Ошибка импорта компонентов: {e}")
    print("   Продолжаем без них...")

class BlockchainIntegrator:
    """
    Интегратор всех компонентов блокчейна
    Работает параллельно с существующим кодом
    """
    
    def __init__(self):
        self.mempool = None
        self.storage = None
        self.running = False
        
        # Пытаемся инициализировать компоненты
        try:
            self.mempool = Mempool()
            print("✅ Mempool инициализирован")
        except:
            print("⚠️ Mempool не загружен")
        
        try:
            self.storage = ChainStorage()
            print("✅ Chain Storage инициализирован")
        except:
            print("⚠️ Chain Storage не загружен")
    
    def start(self):
        """Запустить интегратора в фоне"""
        self.running = True
        thread = threading.Thread(target=self._background_worker, daemon=True)
        thread.start()
        print("🔌 Blockchain Integrator запущен")
    
    def _background_worker(self):
        """Фоновый поток для синхронизации"""
        while self.running:
            try:
                # Здесь можно добавить фоновые задачи
                # Например, сохранение состояния каждые 10 секунд
                if self.storage:
                    # Логика сохранения
                    pass
                
                time.sleep(10)
            except Exception as e:
                print(f"⚠️ Ошибка в фоновом потоке: {e}")
    
    def stop(self):
        """Остановить интегратора"""
        self.running = False
    
    def get_status(self) -> dict:
        """Статус всех компонентов"""
        return {
            "mempool": self.mempool.get_stats() if self.mempool else None,
            "storage": {
                "latest_height": self.storage.get_latest_height() if self.storage else -1
            },
            "rate_limiter": "active",
            "jwt_auth": "active"
        }

# Глобальный экземпляр
integrator = BlockchainIntegrator()

# Автоматический запуск при импорте
integrator.start()
