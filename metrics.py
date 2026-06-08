#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prometheus метрики для мониторинга"""

import time
import threading
from typing import Dict, Any
from collections import defaultdict

class MetricsCollector:
    """Сбор метрик для Prometheus"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = defaultdict(int)
        self.histograms: Dict[str, list] = defaultdict(list)
        self.lock = threading.RLock()
    
    def increment(self, name: str, value: int = 1) -> None:
        """Инкремент метрики"""
        with self.lock:
            self.metrics[name] += value
    
    def gauge(self, name: str, value: float) -> None:
        """Установка gauge метрики"""
        with self.lock:
            self.metrics[name] = value
    
    def observe(self, name: str, value: float) -> None:
        """Добавление значения в гистограмму"""
        with self.lock:
            self.histograms[name].append(value)
            # Ограничиваем размер
            if len(self.histograms[name]) > 1000:
                self.histograms[name] = self.histograms[name][-500:]
    
    def get_metrics(self) -> str:
        """Получение метрик в формате Prometheus"""
        with self.lock:
            lines = []
            
            # Counter метрики
            for name, value in self.metrics.items():
                lines.append(f"{name} {value}")
            
            # Histogram метрики
            for name, values in self.histograms.items():
                if values:
                    avg = sum(values) / len(values)
                    lines.append(f"{name}_avg {avg}")
                    lines.append(f"{name}_count {len(values)}")
                    lines.append(f"{name}_sum {sum(values)}")
            
            return "\n".join(lines)
    
    def get_blockchain_metrics(self, chain_length: int, mempool_size: int, 
                               total_transactions: int) -> Dict[str, Any]:
        """Сбор метрик блокчейна"""
        return {
            'chain_length': chain_length,
            'mempool_size': mempool_size,
            'total_transactions': total_transactions,
            'timestamp': time.time()
        }

metrics = MetricsCollector()
