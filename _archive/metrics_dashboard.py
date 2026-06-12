#!/usr/bin/env python3
"""METRICS DASHBOARD - сбор и визуализация метрик сети"""

import json
import time
import sqlite3
from typing import Dict, List, Any
from datetime import datetime

class MetricsCollector:
    """Сбор метрик для Grafana-подобного дашборда"""
    
    def __init__(self, db_path: str = "blockchain.db"):
        self.db_path = db_path
        self.metrics: Dict[str, List] = {}
    
    def get_network_metrics(self) -> Dict:
        """Сбор основных метрик сети"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # TPS (transactions per second)
            c.execute("SELECT COUNT(*) FROM transactions WHERE timestamp > ?", (int(time.time()) - 60,))
            txs_last_min = c.fetchone()[0]
            tps = txs_last_min / 60
            
            # Блоки в час
            c.execute("SELECT COUNT(*) FROM blocks WHERE timestamp > ?", (int(time.time()) - 3600,))
            blocks_per_hour = c.fetchone()[0]
            
            # Общий газ
            c.execute("SELECT SUM(gas_used) FROM blocks WHERE timestamp > ?", (int(time.time()) - 3600,))
            total_gas = c.fetchone()[0] or 0
            
            # Активные адреса
            c.execute("SELECT COUNT(*) FROM addresses WHERE last_seen > ?", (int(time.time()) - 86400,))
            active_addresses = c.fetchone()[0]
            
            conn.close()
            
            return {
                "tps": round(tps, 2),
                "blocks_per_hour": blocks_per_hour,
                "avg_block_time": round(3600 / max(1, blocks_per_hour), 2),
                "total_gas_hour": total_gas,
                "active_addresses_24h": active_addresses,
                "timestamp": int(time.time())
            }
        except:
            return {
                "tps": 0,
                "blocks_per_hour": 0,
                "avg_block_time": 15,
                "total_gas_hour": 0,
                "active_addresses_24h": 0,
                "timestamp": int(time.time())
            }
    
    def get_gas_stats(self) -> Dict:
        """Статистика газа"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute("SELECT AVG(gas_used), MAX(gas_used), MIN(gas_used) FROM transactions")
            avg_gas, max_gas, min_gas = c.fetchone()
            
            c.execute("SELECT AVG(gas_used) FROM blocks")
            avg_block_gas = c.fetchone()[0] or 0
            
            conn.close()
            
            return {
                "avg_tx_gas": int(avg_gas or 0),
                "max_tx_gas": int(max_gas or 0),
                "min_tx_gas": int(min_gas or 0),
                "avg_block_gas": int(avg_block_gas or 0),
                "base_gas": 21000
            }
        except:
            return {"avg_tx_gas": 21000, "max_tx_gas": 21000, "min_tx_gas": 21000, "avg_block_gas": 0}
    
    def generate_dashboard_html(self) -> str:
        """Генерация HTML дашборда"""
        metrics = self.get_network_metrics()
        gas_stats = self.get_gas_stats()
        
        return f'''
<!DOCTYPE html>
<html>
<head>
    <title>Absolute Blockchain - Network Dashboard</title>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="10">
    <style>
        body {{ font-family: monospace; background: #0a0a0a; color: #0f0; padding: 20px; }}
        h1 {{ color: #0f0; text-align: center; }}
        .dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }}
        .card {{ background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 20px; }}
        .metric {{ font-size: 32px; font-weight: bold; color: #60a5fa; }}
        .label {{ color: #9ca3af; font-size: 12px; }}
        .success {{ color: #34d399; }}
        .warning {{ color: #fbbf24; }}
        .critical {{ color: #f87171; }}
    </style>
</head>
<body>
    <h1>📊 Absolute Blockchain - Network Dashboard</h1>
    <div class="dashboard">
        <div class="card">
            <div class="label">TPS (Transactions/sec)</div>
            <div class="metric">{metrics["tps"]}</div>
        </div>
        <div class="card">
            <div class="label">Blocks per Hour</div>
            <div class="metric">{metrics["blocks_per_hour"]}</div>
        </div>
        <div class="card">
            <div class="label">Avg Block Time</div>
            <div class="metric">{metrics["avg_block_time"]}s</div>
        </div>
        <div class="card">
            <div class="label">Gas Used (last hour)</div>
            <div class="metric">{metrics["total_gas_hour"]:,}</div>
        </div>
        <div class="card">
            <div class="label">Active Addresses (24h)</div>
            <div class="metric">{metrics["active_addresses_24h"]}</div>
        </div>
        <div class="card">
            <div class="label">Avg Gas per Transaction</div>
            <div class="metric">{gas_stats["avg_tx_gas"]:,}</div>
        </div>
        <div class="card">
            <div class="label">Max Gas per Transaction</div>
            <div class="metric">{gas_stats["max_tx_gas"]:,}</div>
        </div>
        <div class="card">
            <div class="label">Base Gas</div>
            <div class="metric">{gas_stats["base_gas"]:,}</div>
        </div>
    </div>
    <p style="text-align:center; margin-top:20px;">Auto-refresh every 10 seconds | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
</body>
</html>
'''

def test_metrics():
    print("📊 Metrics Dashboard Test")
    print("=" * 40)
    
    collector = MetricsCollector()
    metrics = collector.get_network_metrics()
    print(f"   📈 TPS: {metrics['tps']}")
    print(f"   📦 Blocks per hour: {metrics['blocks_per_hour']}")
    print(f"   ⏱️ Avg block time: {metrics['avg_block_time']}s")
    
    gas = collector.get_gas_stats()
    print(f"   ⛽ Avg gas per tx: {gas['avg_tx_gas']}")
    
    # Сохраняем HTML
    html = collector.generate_dashboard_html()
    with open("dashboard.html", "w") as f:
        f.write(html)
    print("   ✅ Dashboard saved to dashboard.html")
    
    return True

if __name__ == "__main__":
    test_metrics()
