#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Автоматическое восстановление при сбоях"""

import os
import sys
import time
import threading
import subprocess
import psutil
from typing import List, Dict, Any

class AutoHeal:
    """Мониторинг и автоматическое восстановление сервисов"""
    
    def __init__(self):
        self.services: Dict[str, Dict[str, Any]] = {}
        self.running = False
        self.monitor_thread = None
    
    def register_service(self, name: str, command: List[str], port: int = None) -> None:
        """Регистрация сервиса для мониторинга"""
        self.services[name] = {
            'command': command,
            'port': port,
            'process': None,
            'last_health_check': 0,
            'failures': 0
        }
    
    def start_service(self, name: str) -> bool:
        """Запуск сервиса"""
        if name not in self.services:
            return False
        
        service = self.services[name]
        try:
            process = subprocess.Popen(
                service['command'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
            )
            service['process'] = process
            service['failures'] = 0
            print(f"✅ Запущен: {name}")
            return True
        except Exception as e:
            print(f"❌ Ошибка запуска {name}: {e}")
            return False
    
    def stop_service(self, name: str) -> bool:
        """Остановка сервиса"""
        if name not in self.services:
            return False
        
        service = self.services[name]
        if service['process']:
            try:
                service['process'].terminate()
                service['process'].wait(timeout=5)
            except:
                service['process'].kill()
            service['process'] = None
            print(f"🛑 Остановлен: {name}")
        return True
    
    def check_service_health(self, name: str) -> bool:
        """Проверка здоровья сервиса"""
        service = self.services[name]
        
        # Проверка процесса
        if service['process']:
            if service['process'].poll() is not None:
                return False
        
        # Проверка порта (если указан)
        if service['port']:
            if not self._check_port(service['port']):
                return False
        
        return True
    
    def _check_port(self, port: int) -> bool:
        """Проверка доступности порта"""
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    
    def _monitor_loop(self):
        """Цикл мониторинга"""
        while self.running:
            for name in list(self.services.keys()):
                if not self.check_service_health(name):
                    print(f"⚠️ Сервис {name} не отвечает! Перезапуск...")
                    self.stop_service(name)
                    time.sleep(2)
                    self.start_service(name)
            
            time.sleep(10)  # Проверка каждые 10 секунд
    
    def start(self):
        """Запуск системы мониторинга"""
        print("🔄 Запуск AutoHeal...")
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop(self):
        """Остановка системы мониторинга"""
        self.running = False
        for name in list(self.services.keys()):
            self.stop_service(name)

# Пример использования
auto_heal = AutoHeal()

if __name__ == '__main__':
    # Регистрация сервисов
    auto_heal.register_service("blockchain", ["python", "node_persistent.py"], port=8080)
    auto_heal.register_service("rpc", ["python", "rpc_proxy.py"], port=8545)
    
    auto_heal.start()
    
    print("AutoHeal запущен. Нажмите Ctrl+C для остановки.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        auto_heal.stop()
