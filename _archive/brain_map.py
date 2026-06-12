#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ETHEREUM BRAIN MAP - Визуализация сети как "мозг"""

import json
from typing import Dict, List, Any

class BrainMap:
    """Создание графа сети для визуализации"""
    
    def __init__(self):
        self.nodes: List[Dict] = []
        self.links: List[Dict] = []
    
    def add_mempool_layer(self, pending_count: int):
        self.nodes.append({
            "id": "mempool",
            "type": "input",
            "label": f"Mempool\n{pending_count} txs",
            "value": min(pending_count / 100, 1)
        })
    
    def add_validator_layer(self, validator_count: int, stake: float):
        self.nodes.append({
            "id": "validators",
            "type": "process",
            "label": f"Validators\n{validator_count} active\n{stake:.0f} stake",
            "value": min(validator_count / 100, 1)
        })
    
    def add_blocks_layer(self, block_count: int, gas_used: int):
        self.nodes.append({
            "id": "blocks",
            "type": "storage",
            "label": f"Blocks\n{block_count} blocks\n{gas_used} gas",
            "value": min(block_count / 1000, 1)
        })
    
    def add_state_layer(self, account_count: int, contract_count: int):
        self.nodes.append({
            "id": "state",
            "type": "output",
            "label": f"State\n{account_count} accounts\n{contract_count} contracts",
            "value": min(account_count / 1000, 1)
        })
    
    def add_connection(self, source: str, target: str, strength: float = 0.5):
        self.links.append({
            "source": source,
            "target": target,
            "strength": strength
        })
    
    def build_full_map(self, stats: Dict) -> Dict:
        """Построение полной карты на основе статистики"""
        self.nodes = []
        self.links = []
        
        # Добавляем слои
        self.add_mempool_layer(stats.get("mempool_size", 0))
        self.add_validator_layer(stats.get("validators", 0), stats.get("total_stake", 0))
        self.add_blocks_layer(stats.get("blocks", 0), stats.get("gas_total", 0))
        self.add_state_layer(stats.get("accounts", 0), stats.get("contracts", 0))
        
        # Добавляем связи
        self.add_connection("mempool", "validators", 0.8)
        self.add_connection("validators", "blocks", 0.9)
        self.add_connection("blocks", "state", 1.0)
        self.add_connection("mempool", "blocks", 0.6)
        
        return {
            "nodes": self.nodes,
            "links": self.links
        }
    
    def generate_html(self, stats: Dict) -> str:
        """Генерация HTML с визуализацией D3.js"""
        graph_data = self.build_full_map(stats)
        graph_json = json.dumps(graph_data, indent=2)
        
        return f'''
<!DOCTYPE html>
<html>
<head>
    <title>Ethereum Brain Map</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; font-family: monospace; }}
        #graph {{ width: 100vw; height: 100vh; background: #0a0a0a; }}
        .node text {{ fill: #0f0; font-size: 12px; }}
        .link {{ stroke: #0f0; stroke-opacity: 0.5; }}
        .tooltip {{ position: absolute; background: #111; border: 1px solid #0f0; padding: 5px; border-radius: 5px; pointer-events: none; }}
    </style>
</head>
<body>
    <div id="graph"></div>
    <script>
        const graphData = {graph_json};
        
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = d3.select("#graph")
            .append("svg")
            .attr("width", width)
            .attr("height", height);
        
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(200))
            .force("charge", d3.forceManyBody().strength(-500))
            .force("center", d3.forceCenter(width / 2, height / 2));
        
        const link = svg.append("g")
            .selectAll("line")
            .data(graphData.links)
            .enter()
            .append("line")
            .attr("class", "link")
            .attr("stroke-width", d => d.strength * 3);
        
        const node = svg.append("g")
            .selectAll("g")
            .data(graphData.nodes)
            .enter()
            .append("g")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
        
        node.append("circle")
            .attr("r", d => 30 + d.value * 30)
            .attr("fill", d => d.type === "input" ? "#0a3a0a" : d.type === "output" ? "#3a0a3a" : "#0a0a3a")
            .attr("stroke", "#0f0")
            .attr("stroke-width", 2);
        
        node.append("text")
            .attr("text-anchor", "middle")
            .attr("dy", ".3em")
            .text(d => d.label)
            .attr("fill", "#0f0")
            .attr("font-size", "12px");
        
        simulation.on("tick", () => {{
            link.attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node.attr("transform", d => `translate(${{d.x}}, ${{d.y}})`);
        }});
        
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}
        
        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}
        
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
    </script>
</body>
</html>
'''

def test_brain_map():
    print("🧠 Ethereum Brain Map")
    print("=" * 40)
    
    brain = BrainMap()
    stats = {
        "mempool_size": 15,
        "validators": 32,
        "total_stake": 1000000,
        "blocks": 500,
        "gas_total": 5000000,
        "accounts": 250,
        "contracts": 12
    }
    
    graph = brain.build_full_map(stats)
    print(f"   📊 Nodes: {len(graph['nodes'])}")
    print(f"   🔗 Links: {len(graph['links'])}")
    
    # Сохраняем HTML
    html = brain.generate_html(stats)
    with open("brain_map.html", "w") as f:
        f.write(html)
    print("   ✅ Brain map saved to brain_map.html")
    
    return True

if __name__ == "__main__":
    test_brain_map()
