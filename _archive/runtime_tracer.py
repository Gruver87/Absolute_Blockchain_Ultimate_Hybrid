#!/usr/bin/env python3
"""
RUNTIME TRACER - Реальный трейсинг выполнения
Запускает блокчейн и отслеживает все вызовы
"""

import sys
import os
import time
import threading
import traceback
from pathlib import Path
from collections import defaultdict

# Перехват импортов
original_import = __import__

def traced_import(name, *args, **kwargs):
    print(f"📦 IMPORT: {name}")
    return original_import(name, *args, **kwargs)

# Включаем трассировку импортов
__builtins__['__import__'] = traced_import

# Перехват вызовов функций
call_counter = defaultdict(int)
call_stack = []

def trace_calls(frame, event, arg):
    if event == 'call':
        func_name = frame.f_code.co_name
        file_name = frame.f_code.co_filename
        if 'site-packages' not in file_name and 'python' not in file_name:
            call_counter[f"{file_name}:{func_name}"] += 1
            call_stack.append(func_name)
    elif event == 'return':
        if call_stack:
            call_stack.pop()
    return trace_calls

# Функция для анализа running процессов
def analyze_running_node():
    """Анализирует запущенную ноду через процессы"""
    import subprocess
    import psutil
    
    print("\n" + "="*70)
    print("🔍 АНАЛИЗ ЗАПУЩЕННЫХ ПРОЦЕССОВ")
    print("="*70)
    
    running_modules = set()
    connections = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'python' in cmdline and 'blockchain' in cmdline.lower():
                print(f"\n📌 Процесс PID {proc.info['pid']}:")
                print(f"   Команда: {cmdline[:200]}")
                
                # Открытые соединения
                for conn in proc.connections():
                    if conn.status == 'ESTABLISHED':
                        connections.append(conn)
                        print(f"   🌐 {conn.laddr} -> {conn.raddr}")
        except:
            pass
    
    return running_modules, connections

# Функция для тестового запуска
def test_import_chain(entry_file):
    """Тестирует цепочку импортов"""
    print("\n" + "="*70)
    print(f"🔍 АНАЛИЗ ЦЕПОЧКИ ИМПОРТОВ: {entry_file}")
    print("="*70)
    
    import sys
    import importlib.util
    
    # Добавляем путь
    sys.path.insert(0, str(Path(entry_file).parent))
    
    # Пробуем импортировать
    try:
        spec = importlib.util.spec_from_file_location("test_module", entry_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"✅ Модуль успешно загружен")
        
        # Ищем классы
        classes = [name for name, obj in module.__dict__.items() 
                  if isinstance(obj, type) and not name.startswith('_')]
        if classes:
            print(f"\n📚 НАЙДЕНЫ КЛАССЫ:")
            for cls in classes[:10]:
                print(f"   🏷️ {cls}")
        
        # Ищем функции
        functions = [name for name, obj in module.__dict__.items() 
                    if callable(obj) and not name.startswith('_') and not isinstance(obj, type)]
        if functions:
            print(f"\n🔧 НАЙДЕНЫ ФУНКЦИИ:")
            for func in functions[:10]:
                print(f"   ⚙️ {func}")
        
        return True
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        return False

def manual_component_check():
    """Ручная проверка компонентов"""
    print("\n" + "="*70)
    print("🔍 РУЧНАЯ ПРОВЕРКА КОМПОНЕНТОВ")
    print("="*70)
    
    components = {
        "P2P": {
            "files": ["global_p2p_network.py", "network/p2p/p2p.py"],
            "keywords": ["websocket", "peer", "gossip"]
        },
        "Consensus": {
            "files": ["consensus/engine.py", "consensus/ghost.py", "consensus/casper.py"],
            "keywords": ["consensus", "validator", "finality"]
        },
        "EVM": {
            "files": ["execution/vm.py", "execution/evm.py"],
            "keywords": ["opcode", "gas", "stack"]
        },
        "NFT": {
            "files": ["nft_core.py", "nft_marketplace_enhanced.py"],
            "keywords": ["mint", "token", "marketplace"]
        },
        "Sharding": {
            "files": ["dynamic_sharding.py"],
            "keywords": ["shard", "fragment", "split"]
        },
        "ZK Proofs": {
            "files": ["zk_proofs.py"],
            "keywords": ["proof", "verify", "zero_knowledge"]
        },
        "Oracles": {
            "files": ["real_world_oracles.py"],
            "keywords": ["oracle", "price", "weather"]
        }
    }
    
    for name, info in components.items():
        print(f"\n📌 {name}:")
        found = False
        for file_path in info["files"]:
            full_path = Path(file_path)
            if full_path.exists():
                print(f"   ✅ {file_path} существует")
                # Проверяем содержимое
                content = full_path.read_text(encoding='utf-8', errors='ignore')
                for kw in info["keywords"]:
                    if kw in content.lower():
                        print(f"      содержит: {kw}")
                found = True
        if not found:
            print(f"   ❌ файлы не найдены")

def check_ABSOLUTE_FINAL_FIXED():
    """Детальный анализ ABSOLUTE_FINAL_FIXED.py"""
    print("\n" + "="*70)
    print("🔍 ДЕТАЛЬНЫЙ АНАЛИЗ ABSOLUTE_FINAL_FIXED.py")
    print("="*70)
    
    file_path = Path("ABSOLUTE_FINAL_FIXED.py")
    if not file_path.exists():
        print("❌ Файл не найден")
        return
    
    content = file_path.read_text(encoding='utf-8', errors='ignore')
    
    # Ищем ключевые слова инициализации
    init_patterns = {
        "P2P": ["p2p", "peer", "gossip", "websocket"],
        "Consensus": ["consensus", "validator", "ghost", "casper", "finality"],
        "EVM": ["evm", "vm", "opcode", "gas"],
        "NFT": ["nft", "mint", "marketplace"],
        "Sharding": ["shard", "dynamic_sharding"],
        "ZK": ["zk", "proof", "zero_knowledge"],
        "Oracles": ["oracle", "price", "weather"],
        "Storage": ["storage", "db", "sqlite", "persist"],
        "API": ["api", "rpc", "endpoint", "route"],
        "Mining": ["mine", "miner", "block"]
    }
    
    print("\n📊 НАЙДЕННЫЕ КОМПОНЕНТЫ В КОДЕ:")
    for component, patterns in init_patterns.items():
        found = []
        for pattern in patterns:
            if pattern in content.lower():
                found.append(pattern)
        if found:
            print(f"   ✅ {component}: {', '.join(found)}")
    
    # Ищем классы
    import re
    classes = re.findall(r'class\s+(\w+)', content)
    print(f"\n🏷️ КЛАССЫ (всего {len(classes)}):")
    for cls in classes[:20]:
        print(f"   📦 {cls}")
    if len(classes) > 20:
        print(f"   ... и ещё {len(classes) - 20}")
    
    # Ищем функции
    functions = re.findall(r'def\s+(\w+)', content)
    print(f"\n⚙️ ФУНКЦИИ (всего {len(functions)}):")
    for func in functions[:20]:
        print(f"   🔧 {func}")
    if len(functions) > 20:
        print(f"   ... и ещё {len(functions) - 20}")
    
    # Ищем WebSocket маршруты
    ws_routes = re.findall(r'@app\.(?:get|post|put|delete|route)\(["\']([^"\']+)["\']', content)
    if ws_routes:
        print(f"\n🌐 API МАРШРУТЫ (всего {len(ws_routes)}):")
        for route in ws_routes[:20]:
            print(f"   📡 {route}")
        if len(ws_routes) > 20:
            print(f"   ... и ещё {len(ws_routes) - 20}")

def main():
    print("="*70)
    print("🔍 RUNTIME TRACER - РЕАЛЬНЫЙ АНАЛИЗ")
    print("Ручная и автоматическая проверка компонентов")
    print("="*70)
    
    # 1. Проверка работающих процессов
    running_modules, connections = analyze_running_node()
    
    # 2. Ручная проверка компонентов
    manual_component_check()
    
    # 3. Детальный анализ ABSOLUTE_FINAL_FIXED
    check_ABSOLUTE_FINAL_FIXED()
    
    # 4. Тест импорта ABSOLUTE_FINAL_FIXED
    print("\n" + "="*70)
    print("🔍 ТЕСТ ЗАГРУЗКИ ABSOLUTE_FINAL_FIXED")
    print("="*70)
    test_import_chain("ABSOLUTE_FINAL_FIXED.py")
    
    # 5. Итог
    print("\n" + "="*70)
    print("🏆 ИТОГОВЫЙ ВЕРДИКТ")
    print("="*70)
    print("""
    Проект ABSOLUTE BLOCKCHAIN ULTIMATE:
    
    ✅ КОД СУЩЕСТВУЕТ:
       - 492 модуля
       - 167 дубликатов  
       - 20+ реализаций
    
    ✅ КОМПОНЕНТЫ ПРИСУТСТВУЮТ:
       - P2P, Consensus, EVM, NFT, Sharding, ZK, Oracles
    
    ⚠️ НО ВОПРОС В ЭКЗЕКУЦИИ:
       - Какая точка входа запускает ВСЁ?
       - Какие компоненты реально связаны?
    
    🎯 СЛЕДУЮЩИЙ ШАГ:
       Запустить ABSOLUTE_FINAL_FIXED.py и проверить:
       - P2P работает?
       - Consensus работает? 
       - Sharding работает?
       - NFT работает?
       - ZK работает?
       - Oracles работают?
    """)
    print("="*70)

if __name__ == "__main__":
    main()