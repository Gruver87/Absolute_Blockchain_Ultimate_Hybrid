# modules/telegram.py
import threading
import time
import json
import urllib.request

class TelegramBot:
    def __init__(self, core, token="8659183710:AAHEBjDxkFZ3fCG_q5zz3ZtiRKvlOjTdGRM"):
        self.core = core
        self.token = token
        self.running = False
        self.offset = 0
        print("   ✅ Telegram Bot initialized")
    
    def start(self):
        self.running = True
        thread = threading.Thread(target=self._poll, daemon=True)
        thread.start()
    
    def _poll(self):
        while self.running:
            try:
                url = f"https://api.telegram.org/bot{self.token}/getUpdates?offset={self.offset}&timeout=30"
                with urllib.request.urlopen(url, timeout=35) as response:
                    data = json.loads(response.read().decode())
                    for update in data.get('result', []):
                        self.offset = update['update_id'] + 1
                        self._handle_update(update)
            except:
                time.sleep(5)
    
    def _handle_update(self, update):
        message = update.get('message', {})
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        if text == '/start':
            self._send_message(chat_id, "🤖 Absolute Blockchain Bot\n\n"
                               "Команды:\n/stats - статистика\n/balance <address> - баланс\n/nft - NFT статистика")
        elif text == '/stats':
            stats = self.core.get_stats()
            msg = f"📊 Статистика блокчейна:\n📦 Блоков: {stats['blocks']}\n💰 Total Supply: {stats['total_supply']:.2f} ABS"
            self._send_message(chat_id, msg)
        elif text.startswith('/balance'):
            parts = text.split()
            if len(parts) > 1:
                addr = parts[1]
                balance = self.core.get_balance(addr)
                self._send_message(chat_id, f"💰 Баланс {addr[:16]}...: {balance:.2f} ABS")
            else:
                self._send_message(chat_id, "Использование: /balance <address>")
        elif text == '/nft':
            from modules.nft import NFTModule
            # Временно
            self._send_message(chat_id, "🖼️ NFT система активна")
    
    def _send_message(self, chat_id, text):
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = json.dumps({'chat_id': chat_id, 'text': text}).encode()
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=10)
        except:
            pass
    
    def stop(self):
        self.running = False
