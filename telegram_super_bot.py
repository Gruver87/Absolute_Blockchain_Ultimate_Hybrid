# telegram_super_bot.py - Telegram бот (без токена в коде!)
import os
import json
import time
import threading

class TelegramBot:
    """Telegram бот - токен берётся из .env"""
    
    def __init__(self):
        # Токен из переменных окружения
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not self.bot_token:
            print("⚠️ TELEGRAM_BOT_TOKEN not set in .env")
            print("   Get token from @BotFather and add to .env")
        
        self.commands = {
            '/start': self.cmd_start,
            '/help': self.cmd_help,
            '/balance': self.cmd_balance,
            '/stats': self.cmd_stats,
            '/nft': self.cmd_nft,
            '/price': self.cmd_price
        }
        self.blockchain = None
        print("🤖 Telegram Bot ready (token from .env)")
    
    def set_blockchain(self, blockchain):
        self.blockchain = blockchain
    
    def cmd_start(self, args) -> str:
        return "🚀 Welcome to Absolute Blockchain!\nUse /help for commands"
    
    def cmd_help(self, args) -> str:
        return """📋 Available commands:
/start - Start bot
/help - Show this help
/balance <address> - Check balance
/stats - Network statistics
/nft - List available NFTs
/price - Crypto prices"""
    
    def cmd_balance(self, args) -> str:
        if not self.blockchain or not args:
            return "Usage: /balance <address>"
        addr = args[0]
        balance = self.blockchain.get_balance(addr)
        return f"💰 Balance of {addr[:10]}...: {balance} ABS"
    
    def cmd_stats(self, args) -> str:
        if not self.blockchain:
            return "Blockchain not connected"
        info = self.blockchain.get_info()
        return f"""📊 Network Statistics:
Blocks: {info['blocks']}
Mempool: {info['mempool_size']}
Contracts: {info.get('contracts', 0)}
Reward: {info['mining_reward']} ABS"""
    
    def cmd_nft(self, args) -> str:
        try:
            from nft_core import nft_marketplace
            stats = nft_marketplace.get_stats()
            return f"""🎨 NFT Marketplace:
Total NFTs: {stats['total_tokens']}
On Sale: {stats['on_sale']}
Unique Owners: {stats['unique_owners']}"""
        except:
            return "NFT module not available"
    
    def cmd_price(self, args) -> str:
        try:
            from real_world_oracles import oracles
            prices = oracles.get_all_prices()
            return f"""💰 Crypto Prices:
ETH: ${prices['eth_usd']:.2f}
BTC: ${prices['btc_usd']:.2f}"""
        except:
            return "Oracles not available"
    
    def process_message(self, text: str) -> str:
        parts = text.strip().split()
        if not parts:
            return "Unknown command"
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd in self.commands:
            return self.commands[cmd](args)
        return f"Unknown command: {cmd}\nUse /help for available commands"

# Глобальный экземпляр
telegram_bot = TelegramBot()
