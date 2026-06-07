import os
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN - TELEGRAM БОТ (ИСПРАВЛЕННАЯ ВЕРСИЯ)
Совместим с твоим API
"""

import requests
import json
import time
import threading
from datetime import datetime

API_URL = "http://localhost:8080"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

class AbsoluteBot:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
        self.last_update = 0
        
    def send_message(self, chat_id, text, parse_mode=None):
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text
            }
            if parse_mode:
                data["parse_mode"] = parse_mode
            response = requests.post(url, json=data, timeout=10)
            return response.json()
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def get_updates(self):
        try:
            url = f"{self.base_url}/getUpdates"
            params = {"offset": self.last_update + 1, "timeout": 30}
            response = requests.get(url, params=params, timeout=35)
            return response.json().get("result", [])
        except:
            return []
    
    def handle_message(self, message):
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip().lower()
        user = message.get("from", {})
        username = user.get("username", user.get("first_name", "User"))
        
        # ========== БЛОКЧЕЙН КОМАНДЫ ==========
        if text == "/start" or text == "/help":
            self.send_message(chat_id, self.get_help_text())
            
        elif text == "/stats":
            self.show_stats(chat_id)
            
        elif text == "/blocks":
            self.show_blocks(chat_id)
            
        elif text.startswith("/block"):
            parts = text.split()
            if len(parts) > 1:
                self.show_block(chat_id, parts[1])
            else:
                self.send_message(chat_id, "❌ Укажите номер блока: /block 0")
                
        elif text.startswith("/balance"):
            parts = text.split()
            if len(parts) > 1:
                self.show_balance(chat_id, parts[1])
            else:
                self.send_message(chat_id, "❌ Укажите адрес: /balance foundation")
                
        elif text == "/peers":
            self.show_peers(chat_id)
            
        elif text == "/validators":
            self.show_validators(chat_id)
            
        elif text == "/stakinginfo":
            self.show_staking_info(chat_id)
            
        # ========== NFT КОМАНДЫ ==========
        elif text == "/nftcollections":
            self.show_nft_collections(chat_id)
            
        elif text == "/nftmarket":
            self.show_nft_marketplace(chat_id)
            
        elif text.startswith("/nft"):
            parts = text.split()
            if len(parts) > 1:
                self.show_nft(chat_id, parts[1])
            else:
                self.send_message(chat_id, "🦋 Укажите адрес: /nft foundation")
                
        # ========== РЫНОК ==========
        elif text.startswith("/price"):
            parts = text.split()
            if len(parts) > 1:
                self.show_price(chat_id, parts[1].upper())
            else:
                self.show_price(chat_id, "ABS")
                
        elif text == "/market":
            self.show_market(chat_id)
            
        # ========== ДРУГИЕ ==========
        elif text == "/about":
            self.send_message(chat_id, self.get_about_text())
            
        else:
            self.send_message(chat_id, "❓ Неизвестная команда. Используй /help")
    
    def get_help_text(self):
        return """
⚡ ABSOLUTE BLOCKCHAIN BOT v2.0

📊 БЛОКЧЕЙН
/stats - статистика
/blocks - последние блоки
/block [номер] - блок по номеру
/balance [адрес] - баланс
/peers - пиры P2P
/validators - список валидаторов
/stakinginfo - статистика стейкинга

🦋 NFT
/nft [адрес] - NFT пользователя
/nftcollections - коллекции
/nftmarket - маркетплейс

📈 РЫНОК
/price [символ] - цена (ABS, BTC, ETH...)
/market - обзор рынка

ℹ️ ИНФО
/about - о проекте
/help - помощь

🔐 DABRANSKI ULADZIMIR PETROVICH | 14.07.1987
        """
    
    def get_about_text(self):
        return """
⚡ ABSOLUTE BLOCKCHAIN

Версия: 15.0
Консенсус: DPoS
TPS: 10,000+
Комиссия: 0.001 ABS
Квантовая защита: SPHINCS+

Модули:
• NFT система (60 героев)
• EVM + WASM
• Lightning Network
• AI агенты
• Кросс-чейн мосты
• Шардинг (64 шарда)
• Plasma Chain
• ZK-Proofs

Основатель: DABRANSKI ULADZIMIR PETROVICH
Дата рождения: 14.07.1987
Город: GRODNO
        """
    
    def show_stats(self, chat_id):
        try:
            response = requests.get(f"{API_URL}/api/stats", timeout=10)
            if response.status_code == 200:
                stats = response.json()
                text = f"""
📊 СТАТИСТИКА БЛОКЧЕЙНА

🏗️ Блоков: {stats.get('blocks', 0)}
💰 Эмиссия: {stats.get('total_supply', 0):,.0f} ABS
⚡ Сложность: {stats.get('difficulty', 1)}
⏳ Ожидание: {stats.get('pending_transactions', 0)} тxs
👥 Валидаторов: {stats.get('validators_count', 0)}
🌍 Пиров: {stats.get('peers', 0)}

🔐 Квантовая защита: SPHINCS+
🎨 NFT: 60 героев
                """
                self.send_message(chat_id, text)
            else:
                self.send_message(chat_id, "❌ Ошибка получения статистики")
        except Exception as e:
            self.send_message(chat_id, f"❌ Ошибка: {str(e)[:100]}")
    
    def show_blocks(self, chat_id):
        try:
            response = requests.get(f"{API_URL}/api/blocks", timeout=10)
            if response.status_code == 200:
                blocks = response.json()
                text = "📦 ПОСЛЕДНИЕ БЛОКИ\n\n"
                for block in blocks[-5:]:
                    text += f"🔹 Блок #{block.get('height', 0)}\n"
                    text += f"   📝 Транзакций: {block.get('transaction_count', 0)}\n"
                    if block.get('timestamp'):
                        text += f"   ⏱️ {datetime.fromtimestamp(block.get('timestamp')).strftime('%H:%M:%S')}\n\n"
                self.send_message(chat_id, text)
            else:
                self.send_message(chat_id, "❌ Ошибка получения блоков")
        except:
            self.send_message(chat_id, "❌ Ошибка получения блоков")
    
    def show_block(self, chat_id, block_num):
        try:
            response = requests.get(f"{API_URL}/api/blocks", timeout=10)
            if response.status_code == 200:
                blocks = response.json()
                block = next((b for b in blocks if b.get('height') == int(block_num)), None)
                if block:
                    text = f"""
📦 БЛОК #{block.get('height')}

🔗 Хеш: {block.get('block_hash', 'unknown')[:32]}...
📝 Транзакций: {block.get('transaction_count', 0)}
⛏️ Майнер: {block.get('miner', 'unknown')[:16]}...
💰 Награда: {block.get('block_reward', 0)} ABS
⏱️ Время: {datetime.fromtimestamp(block.get('timestamp', 0)).strftime('%Y-%m-%d %H:%M:%S')}
                    """
                    self.send_message(chat_id, text)
                else:
                    self.send_message(chat_id, f"❌ Блок #{block_num} не найден")
            else:
                self.send_message(chat_id, "❌ Ошибка получения блока")
        except:
            self.send_message(chat_id, "❌ Ошибка получения блока")
    
    def show_balance(self, chat_id, address):
        try:
            response = requests.get(f"{API_URL}/api/balance?address={address}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                text = f"""
💰 БАЛАНС

📍 Адрес: {address[:24]}...
💎 Баланс: {data.get('balance', 0):,.2f} ABS
                """
                self.send_message(chat_id, text)
            else:
                self.send_message(chat_id, f"❌ Адрес {address[:16]}... не найден")
        except:
            self.send_message(chat_id, "❌ Ошибка получения баланса")
    
    def show_peers(self, chat_id):
        try:
            response = requests.get(f"{API_URL}/api/peers", timeout=10)
            if response.status_code == 200:
                data = response.json()
                peers = data.get('peers', [])
                text = f"🌍 P2P ПИРЫ\n\n📡 Всего пиров: {len(peers)}\n"
                for peer in peers[:10]:
                    text += f"🔗 {peer}\n"
                self.send_message(chat_id, text)
            else:
                self.send_message(chat_id, "❌ Ошибка получения пиров")
        except:
            self.send_message(chat_id, "❌ Ошибка получения пиров")
    
    def show_validators(self, chat_id):
        try:
            response = requests.get(f"{API_URL}/api/validators", timeout=10)
            if response.status_code == 200:
                data = response.json()
                validators = data.get('validators', [])
                text = "⚖️ АКТИВНЫЕ ВАЛИДАТОРЫ\n\n"
                if validators:
                    for v in validators[:10]:
                        text += f"🔹 {v.get('validator_id', '')[:16]}...\n"
                        text += f"   💰 Стейк: {v.get('stake', 0):,.0f} ABS\n\n"
                else:
                    text += "Нет активных валидаторов"
                self.send_message(chat_id, text)
            else:
                self.send_message(chat_id, "❌ Ошибка получения валидаторов")
        except:
            self.send_message(chat_id, "❌ Ошибка получения валидаторов")
    
    def show_staking_info(self, chat_id):
        try:
            response = requests.get(f"{API_URL}/api/staking", timeout=10)
            if response.status_code == 200:
                data = response.json()
                text = f"""
⚡ СТЕЙКИНГ

💰 Всего застейкано: {data.get('total_staked', 0):,.0f} ABS
📈 APY: {data.get('apy', 5)}%
🎯 Мин. стейк: {data.get('min_stake', 100)} ABS
🏆 Валидаторов: {data.get('validators_count', 0)}
                """
                self.send_message(chat_id, text)
            else:
                self.send_message(chat_id, "❌ Ошибка получения стейкинга")
        except:
            self.send_message(chat_id, "❌ Ошибка получения стейкинга")
    
    def show_nft_collections(self, chat_id):
        try:
            response = requests.get(f"{API_URL}/api/nft/collections", timeout=10)
            if response.status_code == 200:
                data = response.json()
                collections = data.get('collections', [])
                text = "🦋 NFT КОЛЛЕКЦИИ\n\n"
                for col in collections[:5]:
                    text += f"📁 {col.get('name', 'Unknown')}\n"
                    text += f"   🎨 NFT: {col.get('total_supply', 0)}\n"
                    text += f"   👑 Создатель: {col.get('creator', '')[:16]}...\n\n"
                self.send_message(chat_id, text)
            else:
                self.send_message(chat_id, "❌ Ошибка получения коллекций")
        except:
            self.send_message(chat_id, "❌ Ошибка получения коллекций")
    
    def show_nft(self, chat_id, address):
        try:
            response = requests.get(f"{API_URL}/api/nft/owner?address={address}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                tokens = data.get('tokens', [])
                if tokens:
                    text = f"🦋 NFT {address[:16]}...\n\n"
                    for token in tokens[:10]:
                        text += f"🎨 {token.get('name', 'Unknown')}\n"
                        text += f"   📍 ID: {token.get('token_id', '')[:16]}...\n"
                        if token.get('price', 0) > 0:
                            text += f"   💰 Цена: {token.get('price', 0)} ABS\n"
                        text += "\n"
                    self.send_message(chat_id, text)
                else:
                    self.send_message(chat_id, f"🦋 У {address[:16]}... нет NFT")
            else:
                self.send_message(chat_id, f"❌ Ошибка получения NFT")
        except:
            self.send_message(chat_id, "❌ Ошибка получения NFT")
    
    def show_nft_marketplace(self, chat_id):
        try:
            response = requests.get(f"{API_URL}/api/nft/listings", timeout=10)
            if response.status_code == 200:
                data = response.json()
                listings = data.get('listings', [])
                if listings:
                    text = "🛒 NFT МАРКЕТПЛЕЙС\n\n"
                    for listing in listings[:5]:
                        text += f"🎨 NFT: {listing.get('token_id', '')[:16]}...\n"
                        text += f"   💰 Цена: {listing.get('price', 0)} ABS\n"
                        text += f"   👤 Продавец: {listing.get('seller', '')[:16]}...\n\n"
                    self.send_message(chat_id, text)
                else:
                    self.send_message(chat_id, "🛒 Нет активных продаж")
            else:
                self.send_message(chat_id, "❌ Ошибка получения маркетплейса")
        except:
            self.send_message(chat_id, "❌ Ошибка получения маркетплейса")
    
    def show_price(self, chat_id, symbol):
        if symbol == "ABS":
            try:
                response = requests.get(f"{API_URL}/api/stats", timeout=10)
                if response.status_code == 200:
                    stats = response.json()
                    supply = stats.get('total_supply', 100000000)
                    text = f"""
📈 ЦЕНА {symbol}

💰 Цена: 0.001 USD (тестовая)
💎 Рыночная капитализация: ${supply * 0.001:,.0f}
📊 Эмиссия: {supply:,.0f} ABS
🔗 Блокчейн: Absolute v15.0
                    """
                    self.send_message(chat_id, text)
                else:
                    self.send_message(chat_id, f"❌ Ошибка получения цены {symbol}")
            except:
                self.send_message(chat_id, f"❌ Ошибка получения цены {symbol}")
        else:
            self.send_message(chat_id, f"📈 {symbol.upper()}: Данные временно недоступны")
    
    def show_market(self, chat_id):
        self.send_message(chat_id, "📊 РЫНОК\n\nABS: $0.001\nBTC: $60,000\nETH: $3,000\n\nДанные обновляются...")
    
    def run(self):
        print("🤖 ABSOLUTE BLOCKCHAIN TELEGRAM BOT v2.0")
        print(f"🔗 API: {API_URL}")
        print("✅ Бот запущен и ожидает сообщения...")
        
        while True:
            try:
                updates = self.get_updates()
                for update in updates:
                    self.last_update = update["update_id"]
                    if "message" in update:
                        self.handle_message(update["message"])
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    bot = AbsoluteBot()
    bot.run()



