"""AI Agent Manager — autonomous trading agents with market analysis."""

import hashlib
import time
from typing import Dict, List, Optional


class AIAgent:
    def __init__(self, agent_id: str, name: str, owner: str,
                 agent_type: str = "transformer"):
        self.agent_id = agent_id
        self.name = name
        self.owner = owner
        self.agent_type = agent_type
        self.status = "active"
        self.created_at = int(time.time())
        self.last_action = self.created_at
        self.performance_score = 0.0
        self.total_profit = 0.0
        self.actions_count = 0
        self.strategy = {
            "type": "arbitrage",
            "risk_level": "medium",
            "max_position": 1000,
        }
        self.memory: List[Dict] = []

    def predict(self, market_data: Dict) -> Dict:
        features = market_data.get("features") or market_data.get("prices", [])
        if not features:
            return {"prediction": 0, "confidence": 0}
        avg = sum(features) / len(features)
        return {
            "prediction": avg,
            "confidence": 0.75,
            "agent_type": self.agent_type,
        }

    def analyze_market(self, data: List[Dict]) -> Dict:
        prices = [d.get("price", 0) for d in data if d.get("price")]
        if len(prices) < 2:
            return {"trend": "neutral", "confidence": 0}
        trend = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
        if trend > 0.05:
            direction = "bullish"
        elif trend < -0.05:
            direction = "bearish"
        else:
            direction = "neutral"
        recommendation = "buy" if trend > 0.02 else "sell" if trend < -0.02 else "hold"
        return {
            "success": True,
            "trend": direction,
            "trend_strength": abs(trend),
            "recommendation": recommendation,
            "price_change_pct": round(trend * 100, 2),
        }

    def execute_trade(self, trade_type: str, amount: float,
                      price: float) -> Dict:
        if amount <= 0 or price <= 0:
            return {"success": False, "error": "Invalid trade parameters"}
        trade_id = hashlib.sha256(
            f"{self.agent_id}_{trade_type}_{time.time()}".encode()
        ).hexdigest()[:16]
        pnl = (price * amount * 0.01) * (1 if trade_type == "buy" else -1)
        self.total_profit += pnl
        self.actions_count += 1
        self.last_action = int(time.time())
        self.performance_score = self.total_profit / max(1, self.actions_count)
        record = {
            "trade_id": trade_id,
            "type": trade_type,
            "amount": amount,
            "price": price,
            "pnl": pnl,
            "timestamp": int(time.time()),
        }
        self.memory.append(record)
        if len(self.memory) > 500:
            self.memory = self.memory[-500:]
        return {"success": True, **record}

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "owner": self.owner[:16] + "...",
            "agent_type": self.agent_type,
            "status": self.status,
            "performance_score": round(self.performance_score, 4),
            "total_profit": round(self.total_profit, 4),
            "actions_count": self.actions_count,
            "created_at": self.created_at,
        }


class AIAgentManager:
    """Manages AI trading agents: create, predict, trade, analyze."""

    def __init__(self):
        self.agents: Dict[str, AIAgent] = {}
        print("[AIAgentManager] Initialized")

    def create_agent(self, name: str, owner: str,
                     agent_type: str = "transformer") -> str:
        agent_id = hashlib.sha256(
            f"{name}{owner}{time.time()}".encode()
        ).hexdigest()[:16]
        agent = AIAgent(agent_id, name, owner, agent_type)
        self.agents[agent_id] = agent
        print(f"[AIAgentManager] Created agent '{name}' ({agent_id}) for {owner[:12]}...")
        return agent_id

    def get_agent(self, agent_id: str) -> Optional[AIAgent]:
        return self.agents.get(agent_id)

    def get_all_agents(self) -> List[Dict]:
        return [a.to_dict() for a in self.agents.values()]

    def get_user_agents(self, owner: str) -> List[Dict]:
        return [a.to_dict() for a in self.agents.values()
                if a.owner == owner or owner in a.owner]

    def predict(self, agent_id: str, market_data: Dict) -> Dict:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": "Agent not found"}
        return agent.predict(market_data)

    def analyze(self, agent_id: str, price_history: List[Dict]) -> Dict:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": "Agent not found"}
        return agent.analyze_market(price_history)

    def trade(self, agent_id: str, trade_type: str,
              amount: float, price: float) -> Dict:
        agent = self.agents.get(agent_id)
        if not agent:
            return {"success": False, "error": "Agent not found"}
        return agent.execute_trade(trade_type, amount, price)

    def deactivate(self, agent_id: str) -> bool:
        agent = self.agents.get(agent_id)
        if not agent:
            return False
        agent.status = "inactive"
        return True

    def get_stats(self) -> Dict:
        active = sum(1 for a in self.agents.values() if a.status == "active")
        total_profit = sum(a.total_profit for a in self.agents.values())
        return {
            "total_agents": len(self.agents),
            "active_agents": active,
            "total_profit": round(total_profit, 4),
            "total_trades": sum(a.actions_count for a in self.agents.values()),
        }
