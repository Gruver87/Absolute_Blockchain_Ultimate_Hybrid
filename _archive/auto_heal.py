#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  ABSOLUTE BLOCKCHAIN - АВТОМАТИЧЕСКАЯ СИСТЕМА ВОССТАНОВЛЕНИЯ
================================================================================
  Мониторинг и автоматический перезапуск зависших компонентов
"""

import os
import sys
import time
import signal
import subprocess
import requests
import threading
import psutil
from datetime import datetime

# Конфигурация
CHECK_INTERVAL = 30  # Проверка каждые 30 секунд
TIMEOUT = 10  # Таймаут ответа API
RESTART_DELAY = 5  # Задержка перед перезапуском

# Модули для мониторинга
MODULES = [
    {"name": "Основной блокчейн", "file": "ABSOLUTE_FINAL.py", "port": 8080, "process": None},
    {"name": "Mega Expansion", "file": "integrate_expansion.py", "port": 8081, "process": None},
    {"name": "Telegram Бот", "file": "telegram_super_bot.py", "port": None, "process": None},
    {"name": "Тестовая сеть", "file": "testnet.py", "port": 8088, "process": None},
    {"name": "Эксплорер", "file": "explorer.py", "port": 8090, "process": None},
    {"name": "GUI", "file": "gui.py", "port": 8091, "process": None},
    {"name": "Мониторинг", "file": "monitor.py", "port": 8092, "process": None},
    {"name": "Mobile API", "file": "mobile_api.py", "port": 8093, "process": None},
    {"name": "Web Server", "file": "web_server.py", "port": 8094, "process": None},
    {"name": "Prometheus", "file": "prometheus_metrics.py", "port": 9090, "process": None},
]

class AutoHealer:
    def __init__(self):
        self.running = True
        self.failures = {}
        self.log_file = "auto_heal.log"
        
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_msg = f"[{timestamp}] [{level}] {message}"
        print(log_msg)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    
    def check_port(self, port):
        """Проверка доступности порта"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except:
            return False
    
    def check_api(self, port):
        """Проверка API через HTTP"""
        try:
            r = requests.get(f"http://localhost:{port}/api/stats", timeout=TIMEOUT)
            return r.status_code == 200
        except:
            return False
    
    def find_process(self, file_name):
        """Поиск процесса по запущенному файлу"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and any(file_name in ' '.join(cmdline) for file_name in [file_name]):
                    return proc
            except:
                continue
        return None
    
    def restart_module(self, module):
        """Перезапуск модуля"""
        self.log(f"🔄 Перезапуск {module['name']}...", "WARNING")
        
        # Убиваем старый процесс
        if module['process']:
            try:
                module['process'].terminate()
                time.sleep(2)
                if module['process'].is_running():
                    module['process'].kill()
            except:
                pass
        
        # Запускаем новый
        try:
            process = subprocess.Popen(
                [sys.executable, module['file']],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            module['process'] = process
            self.log(f"✅ {module['name']} перезапущен", "INFO")
            return True
        except Exception as e:
            self.log(f"❌ Ошибка перезапуска {module['name']}: {e}", "ERROR")
            return False
    
    def check_module(self, module):
        """Проверка состояния модуля"""
        # Проверка по порту
        if module['port']:
            if not self.check_port(module['port']):
                self.log(f"⚠️ {module['name']} (порт {module['port']}) не отвечает", "WARNING")
                self.failures[module['name']] = self.failures.get(module['name'], 0) + 1
                
                if self.failures[module['name']] >= 3:
                    self.restart_module(module)
                    self.failures[module['name']] = 0
                return False
        
        # Проверка через API
        if module['port'] and module['port'] in [8080, 8088, 8090, 8091, 8092, 8093]:
            if not self.check_api(module['port']):
                self.log(f"⚠️ {module['name']} API не отвечает", "WARNING")
                self.failures[module['name']] = self.failures.get(module['name'], 0) + 1
                
                if self.failures[module['name']] >= 3:
                    self.restart_module(module)
                    self.failures[module['name']] = 0
                return False
        
        # Проверка процесса
        process = self.find_process(module['file'])
        if not process:
            self.log(f"⚠️ {module['name']} процесс не найден", "WARNING")
            self.restart_module(module)
            return False
        
        module['process'] = process
        self.failures[module['name']] = 0
        return True
    
    def start_all_modules(self):
        """Запуск всех модулей при старте"""
        self.log("🚀 Запуск всех модулей...", "INFO")
        for module in MODULES:
            if not self.find_process(module['file']):
                self.restart_module(module)
                time.sleep(2)
    
    def get_status(self):
        """Получение статуса всех модулей"""
        status = {}
        for module in MODULES:
            if module['port']:
                status[module['name']] = {
                    "port": module['port'],
                    "active": self.check_port(module['port']),
                    "api": self.check_api(module['port']) if module['port'] in [8080, 8088, 8090, 8091, 8092, 8093] else None
                }
            else:
                process = self.find_process(module['file'])
                status[module['name']] = {
                    "active": process is not None,
                    "pid": process.pid if process else None
                }
        return status
    
    def run(self):
        """Основной цикл мониторинга"""
        self.log("=" * 60, "INFO")
        self.log("🛡️ АВТОМАТИЧЕСКАЯ СИСТЕМА ВОССТАНОВЛЕНИЯ ЗАПУЩЕНА", "INFO")
        self.log("=" * 60, "INFO")
        
        # Запускаем все модули
        self.start_all_modules()
        
        while self.running:
            try:
                status = self.get_status()
                
                # Выводим статус каждые 5 проверок
                if int(time.time()) % (CHECK_INTERVAL * 5) < CHECK_INTERVAL:
                    self.log("📊 ТЕКУЩИЙ СТАТУС:", "INFO")
                    for name, stat in status.items():
                        if stat.get('active'):
                            self.log(f"  ✅ {name}: работает", "INFO")
                        else:
                            self.log(f"  ❌ {name}: НЕ РАБОТАЕТ", "WARNING")
                
                # Проверяем каждый модуль
                for module in MODULES:
                    self.check_module(module)
                
                time.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                self.log("🛑 Остановка системы восстановления", "INFO")
                break
            except Exception as e:
                self.log(f"❌ Ошибка в цикле мониторинга: {e}", "ERROR")
                time.sleep(CHECK_INTERVAL)
    
    def stop(self):
        self.running = False


# Web интерфейс для мониторинга
class HealthServer:
    def __init__(self, healer):
        self.healer = healer
        self.port = 8095
    
    def start(self):
        from http.server import HTTPServer, BaseHTTPRequestHandler
        
        class Handler(BaseHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.healer = healer
                super().__init__(*args, **kwargs)
            
            def log_message(self, format, *args):
                pass
            
            def do_GET(self):
                if self.path == '/':
                    self._send_html(self._get_html())
                elif self.path == '/api/health':
                    self._send_json(self.healer.get_status())
                elif self.path == '/api/restart':
                    module = self.path.split('=')[-1] if '=' in self.path else None
                    if module:
                        for m in MODULES:
                            if m['name'] == module:
                                self.healer.restart_module(m)
                                self._send_json({'success': True, 'module': module})
                                return
                    self._send_json({'success': False, 'error': 'Module not found'})
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def _send_json(self, data):
                import json
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            
            def _send_html(self, html):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(html.encode())
            
            def _get_html(self):
                return '''
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Auto Heal - Blockchain Monitor</title>
                    <style>
                        body { font-family: monospace; background: #0a0a2a; color: white; padding: 20px; }
                        h1 { color: #ffd700; }
                        .status { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 10px; }
                        .online { background: #00ff88; }
                        .offline { background: #ff4444; }
                        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
                        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #333; }
                        th { color: #ffd700; }
                        button { background: #ffd700; color: #000; border: none; padding: 5px 15px; cursor: pointer; border-radius: 5px; }
                        button:hover { background: #ffaa00; }
                    </style>
                </head>
                <body>
                    <h1>🛡️ Auto Heal - Мониторинг блокчейна</h1>
                    <div id="status"></div>
                    <script>
                        async function loadStatus() {
                            const res = await fetch('/api/health');
                            const data = await res.json();
                            let html = '<table><tr><th>Модуль</th><th>Статус</th><th>Порт/PID</th><th>Действие</th></tr>';
                            for (const [name, info] of Object.entries(data)) {
                                const isOnline = info.active || info.api === true;
                                html += `
                                    <tr>
                                        <td>${name}</td>
                                        <td><span class="status ${isOnline ? 'online' : 'offline'}"></span>${isOnline ? 'ONLINE' : 'OFFLINE'}</td>
                                        <td>${info.port || info.pid || '-'}</td>
                                        <td><button onclick="restart('${name}')">Перезапустить</button></td>
                                    </tr>
                                `;
                            }
                            html += '</table>';
                            document.getElementById('status').innerHTML = html;
                        }
                        
                        async function restart(module) {
                            if(confirm(`Перезапустить ${module}?`)) {
                                await fetch(`/api/restart?module=${encodeURIComponent(module)}`);
                                setTimeout(loadStatus, 2000);
                            }
                        }
                        
                        loadStatus();
                        setInterval(loadStatus, 5000);
                    </script>
                </body>
                </html>
                '''
        
        server = HTTPServer(('0.0.0.0', self.port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"🛡️ Health Server started on http://localhost:{self.port}")
        print(f"   Мониторинг: http://localhost:{self.port}")
        return server


if __name__ == "__main__":
    import socket
    import threading
    
    print("\n" + "=" * 60)
    print("  ABSOLUTE BLOCKCHAIN - AUTO HEAL SYSTEM")
    print("=" * 60)
    
    healer = AutoHealer()
    
    # Запускаем веб-интерфейс для мониторинга
    health_server = HealthServer(healer)
    health_server.start()
    
    # Запускаем авто-восстановление
    try:
        healer.run()
    except KeyboardInterrupt:
        print("\n🛑 Auto Heal остановлен")