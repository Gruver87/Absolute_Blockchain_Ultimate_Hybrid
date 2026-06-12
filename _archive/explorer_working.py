#!/usr/bin/env python3
"""Absolute Blockchain Explorer - Working Version"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import urllib.request

RPC_URL = "http://localhost:8545"

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Absolute Blockchain Explorer</title>
    <meta charset="UTF-8">
    <style>
        body { font-family: monospace; background: #0a0a0a; color: #0f0; padding: 20px; }
        h1 { color: #0f0; }
        .online { background: #0a3a0a; border: 1px solid #0f0; color: #0f0; padding: 10px; margin: 10px 0; }
        .offline { background: #3a0a0a; border: 1px solid #f00; color: #f00; padding: 10px; margin: 10px 0; }
        .block { border: 1px solid #0f0; margin: 10px 0; padding: 10px; border-radius: 5px; }
        .info { display: inline-block; margin: 5px; padding: 5px 10px; background: #1a1a1a; border-radius: 5px; }
        button { background: #0a0a0a; color: #0f0; border: 1px solid #0f0; padding: 5px 10px; cursor: pointer; }
        input { background: #1a1a1a; color: #0f0; border: 1px solid #0f0; padding: 5px; width: 400px; }
    </style>
</head>
<body>
    <h1>🔗 Absolute Blockchain Explorer</h1>
    <div id="status" class="offline">🔌 Connecting...</div>
    
    <div class="info">📦 Height: <span id="blockNumber">?</span></div>
    <div class="info">🔗 Chain: <span id="chainId">?</span></div>
    <div class="info">⛽ Gas: <span id="gasPrice">?</span> Gwei</div>
    <div class="info">📋 Mempool: <span id="mempool">?</span></div>
    
    <button onclick="refresh()">🔄 Refresh</button>
    <hr>
    
    <h2>🔎 Search</h2>
    <input type="text" id="searchInput" placeholder="Block height, hash or address...">
    <button onclick="search()">Search</button>
    <div id="searchResult"></div>
    
    <h2>📦 Latest Blocks</h2>
    <div id="blocks">Loading...</div>
    
    <h2>⏳ Pending Transactions</h2>
    <div id="mempoolTxs">Loading...</div>
    
    <script>
        const RPC = 'http://localhost:8545';
        
        async function call(method, params=[]) {
            try {
                const res = await fetch(RPC, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({jsonrpc: '2.0', method, params, id: 1})
                });
                const data = await res.json();
                return data.result;
            } catch(e) {
                console.error(e);
                return null;
            }
        }
        
        async function refresh() {
            try {
                const blockNum = await call('eth_blockNumber');
                const chainId = await call('net_version');
                const gasPrice = await call('eth_gasPrice');
                const mempool = await call('txpool_status');
                
                if (blockNum !== null) {
                    document.getElementById('status').innerHTML = '✅ Node Online (Port 8545)';
                    document.getElementById('status').className = 'online';
                    document.getElementById('blockNumber').innerText = parseInt(blockNum, 16);
                    document.getElementById('chainId').innerText = parseInt(chainId, 16);
                    document.getElementById('gasPrice').innerText = parseInt(gasPrice, 16);
                    document.getElementById('mempool').innerText = mempool?.pending || 0;
                    await loadBlocks(parseInt(blockNum, 16));
                } else {
                    throw new Error('No response');
                }
            } catch(e) {
                document.getElementById('status').innerHTML = '❌ Node Offline - Make sure node_persistent.py is running';
                document.getElementById('status').className = 'offline';
            }
        }
        
        async function loadBlocks(maxBlock) {
            const blocksDiv = document.getElementById('blocks');
            blocksDiv.innerHTML = 'Loading blocks...';
            let html = '';
            
            const start = Math.max(0, maxBlock - 9);
            for (let i = maxBlock; i >= start; i--) {
                const block = await call('eth_getBlockByNumber', ['0x' + i.toString(16), true]);
                if (block) {
                    html += `<div class="block">
                        <b>🔷 Block #${parseInt(block.number, 16)}</b>
                        <div>Hash: ${block.hash.substring(0, 30)}...</div>
                        <div>Miner: ${block.miner ? block.miner.substring(0, 20) + '...' : 'Unknown'}</div>
                        <div>📝 Txns: ${block.transactions?.length || 0}</div>
                        <div>⛽ Gas: ${parseInt(block.gasUsed || '0x0', 16)}</div>
                    </div>`;
                }
            }
            blocksDiv.innerHTML = html || '<p>No blocks found</p>';
        }
        
        async function search() {
            const query = document.getElementById('searchInput').value.trim();
            if (!query) return;
            
            const resultDiv = document.getElementById('searchResult');
            resultDiv.innerHTML = 'Searching...';
            
            // Try as block height
            const height = parseInt(query);
            if (!isNaN(height)) {
                const block = await call('eth_getBlockByNumber', ['0x' + height.toString(16), true]);
                if (block) {
                    resultDiv.innerHTML = `<div class="block">
                        <b>Block #${height}</b>
                        <div>Hash: ${block.hash}</div>
                        <div>Timestamp: ${new Date(parseInt(block.timestamp, 16) * 1000)}</div>
                        <div>Transactions: ${block.transactions?.length || 0}</div>
                    </div>`;
                    return;
                }
            }
            
            // Try as block hash
            let block = await call('eth_getBlockByHash', [query, true]);
            if (block) {
                resultDiv.innerHTML = `<div class="block">
                    <b>Block ${block.hash}</b>
                    <div>Height: ${parseInt(block.number, 16)}</div>
                </div>`;
                return;
            }
            
            resultDiv.innerHTML = '<div class="block">❌ Not found</div>';
        }
        
        refresh();
        setInterval(refresh, 5000);
    </script>
</body>
</html>
'''

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(HTML.encode())
    
    def log_message(self, format, *args):
        pass  # Тишина в логах

print("=" * 50)
print("🔍 ABSOLUTE BLOCKCHAIN EXPLORER")
print("=" * 50)
print(f"📡 RPC: {RPC_URL}")
print("🌐 http://localhost:8095")
print("=" * 50)
print("✅ Ready! Open http://localhost:8095 in browser")
print("Press Ctrl+C to stop")

HTTPServer(('', 8095), Handler).serve_forever()
