#!/usr/bin/env python3
"""
AUTOMATIC BLOCKCHAIN LAUNCHER & ANALYZER
Запускает блокчейн и определяет реально работающие компоненты
"""

import subprocess
import sys
import time
import requests
import json
import threading
import os
from pathlib import Path

# Конфигурация
ROOT = Path(r"C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate")
os.chdir(ROOT)

# Возможные точки входа (проверяем в порядке приоритета)
ENTRY_CANDIDATES = [
    "node_persistent.py",
    "ABSOLUTE_FINAL_FIXED.py",
    "main.py",
    "run_unified.py"
]

def check_port(port, timeout=2):
    """Проверяет, слушает ли порт"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def test_endpoint(url, timeout=3):
    """Тестирует API эндпоинт"""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except:
        return False

def find_best_entry():
    """Находит лучшую точку входа"""
    print("\n" + "="*70)
    print("🔍 ПОИСК ТОЧКИ ВХОДА")
    print("="*70)
    
    for entry in ENTRY_CANDIDATES:
        if (ROOT / entry).exists():
            # Быстрый анализ содержимого
            content = (ROOT / entry).read_text(encoding='utf-8', errors='ignore')
            
            # Оцениваем качество
            score = 0
            if 'if __name__ == "__main__"' in content:
                score += 1
            if 'Thread' in content or 'threading' in content:
                score += 1
            if 'start' in content and 'serve' in content:
                score += 1
            if 'mining' in content.lower() or 'mine_block' in content:
                score += 2
            
            print(f"\n📄 {entry}: оценка {score}")
            if score >= 2:
                print(f"   ✅ РЕКОМЕНДОВАН (использует потоки/майнинг)")
                return entry
    
    return ENTRY_CANDIDATES[0] if (ROOT / ENTRY_CANDIDATES[0]).exists() else None

def analyze_running_node():
    """Анализирует работу запущенной ноды"""
    print("\n" + "="*70)
    print("📊 АНАЛИЗ РАБОТАЮЩЕЙ НОДЫ")
    print("="*70)
    
    results = {}
    
    # Проверка портов
    ports = {
        8545: "RPC",
        8080: "Web API",
        8081: "Extended API",
        8546: "WebSocket"
    }
    
    print("\n🔌 ПРОВЕРКА ПОРТОВ:")
    for port, name in ports.items():
        is_open = check_port(port)
        status = "✅" if is_open else "❌"
        print(f"   {status} {name}: {port} - {'работает' if is_open else 'не отвечает'}")
        results[f"{name}_port"] = is_open
    
    # Проверка API
    print("\n🌐 ПРОВЕРКА API:")
    
    # JSON-RPC
    rpc_url = "http://localhost:8545"
    try:
        payload = {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
        response = requests.post(rpc_url, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            block_num = int(data.get("result", "0x0"), 16)
            print(f"   ✅ JSON-RPC работает, высота блока: {block_num}")
            results["rpc_working"] = True
            results["block_height"] = block_num
        else:
            print(f"   ❌ JSON-RPC ошибка: {response.status_code}")
            results["rpc_working"] = False
    except Exception as e:
        print(f"   ❌ JSON-RPC не отвечает: {e}")
        results["rpc_working"] = False
    
    # Web API
    web_url = "http://localhost:8080"
    if test_endpoint(web_url):
        print(f"   ✅ Web API работает")
        results["web_api_working"] = True
    else:
        print(f"   ❌ Web API не отвечает")
        results["web_api_working"] = False
    
    return results

def test_transaction():
    """Тестирует отправку транзакции"""
    print("\n" + "="*70)
    print("💸 ТЕСТ ТРАНЗАКЦИИ")
    print("="*70)
    
    try:
        tx_data = {
            "from": "0x1234567890123456789012345678901234567890",
            "to": "0x0987654321098765432109876543210987654321",
            "value": "0x64",
            "gas": "0x5208",
            "gasPrice": "0x3B9ACA00"
        }
        
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_sendTransaction",
            "params": [tx_data],
            "id": 1
        }
        
        response = requests.post("http://localhost:8545", json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                print(f"   ✅ Транзакция отправлена: {data['result'][:20]}...")
                return True
            else:
                print(f"   ⚠️ Ответ RPC: {data}")
        else:
            print(f"   ❌ Ошибка: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Не удалось отправить транзакцию: {e}")
    
    return False

def check_components_runtime():
    """Проверяет компоненты через API"""
    print("\n" + "="*70)
    print("🧩 ПРОВЕРКА КОМПОНЕНТОВ")
    print("="*70)
    
    components_status = {}
    
    # Пробуем разные эндпоинты
    endpoints = [
        ("/health", "Базовый статус"),
        ("/api/stats", "Статистика"),
        ("/api/blocks", "Блоки"),
        ("/api/mempool", "Mempool"),
        ("/api/peers", "P2P пиры"),
        ("/api/nft/collection", "NFT коллекция"),
        ("/api/sharding/stats", "Шардинг"),
        ("/api/oracle/price?symbol=bitcoin", "Оракул"),
    ]
    
    base_url = "http://localhost:8080"
    
    for endpoint, name in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                print(f"   ✅ {name}: работает")
                components_status[name] = True
            else:
                print(f"   ❌ {name}: {response.status_code}")
                components_status[name] = False
        except:
            print(f"   ❌ {name}: не доступен")
            components_status[name] = False
    
    return components_status

def launch_and_monitor(entry_file):
    """Запускает блокчейн и мониторит"""
    print("\n" + "="*70)
    print(f"🚀 ЗАПУСК БЛОКЧЕЙНА: {entry_file}")
    print("="*70)
    
    # Запускаем процесс
    process = subprocess.Popen(
        [sys.executable, entry_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=ROOT
    )
    
    print("\n⏳ Ожидание запуска сервисов...")
    
    # Ждём запуска
    max_wait = 30
    for i in range(max_wait):
        time.sleep(1)
        if check_port(8545) or check_port(8080):
            print(f"   ✅ Сервисы запущены через {i+1} секунд")
            break
        if i % 5 == 0:
            print(f"   ⏳ Ожидание... ({i+1}/{max_wait})")
    else:
        print("   ❌ Таймаут ожидания")
        process.terminate()
        return False
    
    # Даём время на инициализацию
    time.sleep(3)
    
    # Анализируем
    analysis = analyze_running_node()
    components = check_components_runtime()
    
    if analysis.get("rpc_working"):
        test_transaction()
    
    print("\n" + "="*70)
    print("🏆 ИТОГОВЫЙ ОТЧЁТ")
    print("="*70)
    
    working = []
    not_working = []
    
    # Оцениваем компоненты
    if components.get("Базовый статус"):
        working.append("✅ Node Health")
    else:
        not_working.append("❌ Node Health")
    
    if components.get("Статистика"):
        working.append("✅ Blockchain Stats")
    else:
        not_working.append("❌ Blockchain Stats")
    
    if components.get("Блоки"):
        working.append("✅ Block Explorer")
    else:
        not_working.append("❌ Block Explorer")
    
    if components.get("Mempool"):
        working.append("✅ Mempool")
    else:
        not_working.append("❌ Mempool")
    
    if components.get("P2P пиры"):
        working.append("✅ P2P Network")
    else:
        not_working.append("❌ P2P Network")
    
    if components.get("NFT коллекция"):
        working.append("✅ NFT Marketplace")
    else:
        not_working.append("❌ NFT Marketplace")
    
    if components.get("Шардинг"):
        working.append("✅ Sharding")
    else:
        not_working.append("❌ Sharding")
    
    if components.get("Оракул"):
        working.append("✅ Oracles")
    else:
        not_working.append("❌ Oracles")
    
    print(f"\n✅ РАБОТАЕТ ({len(working)}):")
    for w in working:
        print(f"   {w}")
    
    print(f"\n❌ НЕ РАБОТАЕТ ({len(not_working)}):")
    for n in not_working:
        print(f"   {n}")
    
    print(f"\n📊 ВЫСОТА БЛОКА: {analysis.get('block_height', 0)}")
    
    print("\n" + "="*70)
    print("🛑 ОСТАНОВКА НОДЫ...")
    process.terminate()
    time.sleep(2)
    process.kill()
    
    return analysis, components

def main():
    print("="*70)
    print("🤖 АВТОМАТИЧЕСКИЙ АНАЛИЗАТОР БЛОКЧЕЙНА")
    print("Запуск -> Тестирование -> Отчёт")
    print("="*70)
    
    # Находим лучшую точку входа
    entry = find_best_entry()
    if not entry:
        print("\n❌ Не найдена точка входа!")
        return
    
    print(f"\n🎯 Выбрана точка входа: {entry}")
    
    # Запускаем и анализируем
    launch_and_monitor(entry)
    
    print("\n" + "="*70)
    print("✅ АНАЛИЗ ЗАВЕРШЁН")
    print("="*70)

if __name__ == "__main__":
    main()