#!/usr/bin/env python3
"""
ABSOLUTE BLOCKCHAIN - НОВЫЙ ЕДИНЫЙ ENTRYPOINT
Запускает чистую архитектуру, не трогая старые файлы

Старые entrypoints (node_persistent.py, ABSOLUTE_FINAL_FIXED.py и др.)
остаются нетронутыми и могут быть запущены отдельно.
"""

import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Импортируем новую архитектуру
from runtime.orchestrator import Orchestrator

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║     ABSOLUTE BLOCKCHAIN - NEW UNIFIED CLIENT                    ║
║     Старые entrypoints остались нетронутыми                     ║
║     Этот клиент - чистая архитектура                            ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    try:
        orchestrator = Orchestrator()
        orchestrator.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        orchestrator.stop()
