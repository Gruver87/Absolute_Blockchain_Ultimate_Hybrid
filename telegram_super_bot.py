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

    def _api_get(self, path: str, timeout: int = 10):
        try:
            r = requests.get(f"{API_URL}{path}", timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            print(f"[Telegram] API {path}: {e}")
        return None

    def _resolve_address(self, address: str) -> str:
        low = (address or "").strip().lower()
        if low in ("foundation", "founder", "dup", "d.u.p."):
            st = self._api_get("/founder") or self._api_get("/status") or {}
            return st.get("founder_address") or st.get("address") or address
        return address

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

        elif text.startswith("/weather"):
            parts = text.split(maxsplit=1)
            city = parts[1] if len(parts) > 1 else "Grodno"
            self.show_weather(chat_id, city)
            
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
/weather [город] - погода (оракул)

ℹ️ ИНФО
/about - о проекте
/help - помощь

🔐 DABRANSKI ULADZIMIR PETROVICH | 14.07.1987
        """
    
    def get_about_text(self):
        return """
⚡ ABSOLUTE BLOCKCHAIN

Версия: 1.2.0-industrial
Консенсус: PoS (LMD-GHOST + Casper FFG)
TPS: educational devnet
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
        st = self._api_get("/status")
        if not st:
            self.send_message(chat_id, "❌ Нода недоступна — запустите main.py")
            return
        text = f"""📊 СТАТИСТИКА ABSOLUTE

🏗️ Высота: {st.get('height', 0)}
💰 Max supply: {st.get('max_supply', 0):,.0f} ABS
⏳ Mempool: {st.get('mempool_size', 0)} tx
👥 Валидаторов: {st.get('validator_count', 0)}
🌍 Пиров: {st.get('peers', 0)}
🔥 Сожжено: {st.get('total_burned', 0):.4f} ABS
📦 Версия: {st.get('node_version', '?')}
👤 Founder: {st.get('founder_initials', 'D.U.P.')}"""
        self.send_message(chat_id, text)

    def show_blocks(self, chat_id):
        data = self._api_get("/blocks?limit=5")
        if not data:
            self.send_message(chat_id, "❌ Ошибка /blocks")
            return
        blocks = data.get("blocks", [])
        text = "📦 ПОСЛЕДНИЕ БЛОКИ\n\n"
        for block in blocks:
            h = block.get("height", block.get("number", 0))
            txs = block.get("tx_count", block.get("transaction_count", len(block.get("transactions", []))))
            text += f"🔹 #{h} — {txs} tx\n"
        self.send_message(chat_id, text or "Нет блоков")

    def show_block(self, chat_id, block_num):
        blk = self._api_get(f"/blocks/{block_num}")
        if not blk:
            self.send_message(chat_id, f"❌ Блок #{block_num} не найден")
            return
        text = f"""📦 БЛОК #{blk.get('height', block_num)}

🔗 {str(blk.get('hash', ''))[:32]}...
📝 tx: {blk.get('tx_count', len(blk.get('transactions', [])))}
⛏️ {str(blk.get('miner', blk.get('proposer', '')))[:20]}..."""
        self.send_message(chat_id, text)

    def show_balance(self, chat_id, address):
        addr = self._resolve_address(address)
        data = self._api_get(f"/wallet/balance/{addr}")
        if not data:
            data = self._api_get(f"/state/balance/{addr}")
        if not data:
            self.send_message(chat_id, f"❌ Баланс для {addr[:16]}... недоступен")
            return
        bal = data.get("balance", 0)
        self.send_message(chat_id, f"💰 {addr[:20]}...\n💎 {bal:,.6f} ABS")

    def show_peers(self, chat_id):
        data = self._api_get("/network/peers") or {}
        peers = data.get("peers", [])
        text = f"🌍 P2P: {data.get('count', len(peers))} пиров\n"
        for p in peers[:10]:
            if isinstance(p, dict):
                text += f"🔗 {p.get('host', '?')}:{p.get('port', '?')}\n"
            else:
                text += f"🔗 {p}\n"
        if not peers:
            text += "\nSolo mode — нормально для одной ноды."
        self.send_message(chat_id, text)

    def show_validators(self, chat_id):
        data = self._api_get("/validators") or {}
        validators = data.get("validators", [])
        text = f"⚖️ ВАЛИДАТОРЫ ({data.get('count', len(validators))})\n\n"
        for v in validators[:10]:
            addr = v.get("address", v.get("validator_id", ""))[:20]
            stake = v.get("stake", 0)
            text += f"🔹 {addr}... stake={stake:,.0f}\n"
        self.send_message(chat_id, text or "Нет валидаторов")

    def show_staking_info(self, chat_id):
        val = self._api_get("/validators") or {}
        pools = self._api_get("/pools/locks") or {}
        text = f"""⚡ СТЕЙКИНГ / POOLS

🏆 Валидаторов: {val.get('count', 0)}
🎯 Min stake: {val.get('min_stake', 1000)} ABS
🔒 Pool locks: {len(pools.get('locks', pools) if isinstance(pools, dict) else [])}"""
        self.send_message(chat_id, text)

    def show_nft_collections(self, chat_id):
        data = self._api_get("/nft") or self._api_get("/nft/marketplace") or {}
        tokens = data.get("tokens", data.get("nfts", []))
        text = f"🦋 NFT ({len(tokens)} genesis/market)\n"
        for t in (tokens if isinstance(tokens, list) else [])[:5]:
            if isinstance(t, dict):
                text += f"🎨 {t.get('name', t.get('token_id', '?'))}\n"
        self.send_message(chat_id, text or "NFT пусто")

    def show_nft(self, chat_id, address):
        addr = self._resolve_address(address)
        data = self._api_get(f"/nft/owner/{addr}") or self._api_get("/nft")
        tokens = []
        if isinstance(data, dict):
            tokens = data.get("tokens", data.get("nfts", []))
        if not tokens:
            self.send_message(chat_id, f"🦋 У {addr[:16]}... нет NFT")
            return
        text = f"🦋 NFT {addr[:16]}...\n\n"
        for token in tokens[:8]:
            if isinstance(token, dict):
                text += f"🎨 {token.get('name', token.get('token_id', '?'))}\n"
        self.send_message(chat_id, text)

    def show_nft_marketplace(self, chat_id):
        data = self._api_get("/nft/listings") or {}
        listings = data.get("listings", [])
        if not listings:
            self.send_message(chat_id, "🛒 Нет активных листингов")
            return
        text = "🛒 NFT МАРКЕТ\n\n"
        for L in listings[:5]:
            text += f"🎨 {str(L.get('token_id', ''))[:16]}... — {L.get('price', 0)} ABS\n"
        self.send_message(chat_id, text)

    def show_price(self, chat_id, symbol):
        sym = symbol.upper()
        cg_map = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "DOGE": "dogecoin", "ABS": "absolute"}
        prices = self._api_get("/oracles/prices") or {}
        for p in prices.get("prices", []):
            ps = (p.get("symbol") or "").lower()
            if ps == cg_map.get(sym, sym.lower()) or (sym == "ABS" and ps == "absolute"):
                src = p.get("source", "api")
                self.send_message(
                    chat_id,
                    f"📈 {sym}\n💵 ${p.get('price', 0):,.4f}\n"
                    f"24h: {p.get('change_24h', 0):+.2f}%\n📡 source: {src}",
                )
                return
        self.send_message(chat_id, f"❌ Цена {sym} недоступна (оракул / сеть)")

    def show_market(self, chat_id):
        prices = self._api_get("/oracles/prices")
        if not prices:
            self.send_message(chat_id, "❌ /oracles/prices недоступен")
            return
        text = "📊 РЫНОК (live oracles)\n\n"
        for p in prices.get("prices", [])[:6]:
            sym = (p.get("symbol") or "?").upper()
            text += f"{sym}: ${p.get('price', 0):,.4f} ({p.get('source', '?')})\n"
        self.send_message(chat_id, text)

    def show_weather(self, chat_id, city):
        data = self._api_get(f"/oracles/weather?city={city}")
        if not data or data.get("error"):
            self.send_message(chat_id, f"❌ Погода {city}: {data.get('error', 'нет данных') if data else 'API off'}")
            return
        self.send_message(
            chat_id,
            f"🌤 {data.get('city', city)}\n"
            f"🌡 {data.get('temperature')}°C — {data.get('condition')}\n"
            f"💧 {data.get('humidity')}% | source: {data.get('source', 'api')}",
        )
    
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




