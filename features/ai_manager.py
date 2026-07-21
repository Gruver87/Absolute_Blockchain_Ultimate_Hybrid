"""AI Agent Manager — trading agents with SQLite persistence (Wave 43)."""

from crypto import native
import json
import time
from typing import Any, Callable, Dict, List, Optional


class AIAgent:
    def __init__(self, agent_id: str, name: str, owner: str,
                 agent_type: str = "transformer",
                 status: str = "active",
                 created_at: int = None,
                 last_action: int = None,
                 performance_score: float = 0.0,
                 total_profit: float = 0.0,
                 actions_count: int = 0,
                 strategy: Dict = None,
                 memory: List[Dict] = None):
        self.agent_id = agent_id
        self.name = name
        self.owner = owner
        self.agent_type = agent_type
        self.status = status
        self.created_at = created_at if created_at is not None else int(time.time())
        self.last_action = last_action if last_action is not None else self.created_at
        self.performance_score = performance_score
        self.total_profit = total_profit
        self.actions_count = actions_count
        self.strategy = strategy or {
            "type": "arbitrage",
            "risk_level": "medium",
            "max_position": 1000,
        }
        self.memory: List[Dict] = list(memory or [])

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
        return {"success": False, "error": "Trade execution backend not configured"}

    def record_executed_trade(
        self,
        trade_type: str,
        amount: float,
        price: float,
        execution: Dict[str, Any],
    ) -> Dict:
        if not isinstance(execution, dict) or not execution.get("success"):
            return {"success": False, "error": "Trade execution was not successful"}
        status = str(execution.get("status", "filled")).lower()
        if status not in ("filled", "executed", "settled"):
            return {"success": False, "error": f"Trade execution not final: {status}"}
        trade_id = str(execution.get("trade_id") or native.sha256_hex(
            f"{self.agent_id}_{trade_type}_{time.time_ns()}".encode()
        )[:16])
        pnl = float(execution.get("pnl", 0.0))
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
            "venue": execution.get("venue", ""),
            "execution_status": execution.get("status", "filled"),
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
            "owner": self.owner[:16] + "..." if len(self.owner) > 20 else self.owner,
            "agent_type": self.agent_type,
            "status": self.status,
            "performance_score": round(self.performance_score, 4),
            "total_profit": round(self.total_profit, 4),
            "actions_count": self.actions_count,
            "created_at": self.created_at,
        }

    def to_db(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "owner": self.owner,
            "agent_type": self.agent_type,
            "status": self.status,
            "created_at": self.created_at,
            "last_action": self.last_action,
            "performance_score": self.performance_score,
            "total_profit": self.total_profit,
            "actions_count": self.actions_count,
            "strategy": self.strategy,
            "memory": self.memory,
        }


class AIAgentManager:
    """Manages AI trading agents — persisted in SQLite."""

    CREATE_FEE = 0.01

    def __init__(self, db=None, trade_executor: Optional[Callable[[Dict], Dict]] = None):
        self.db = db
        self.trade_executor = trade_executor
        self.agents: Dict[str, AIAgent] = {}
        self._load_from_db()
        print(f"[AIAgentManager] Initialized ({len(self.agents)} agents, "
              f"persisted={bool(db)})")

    def _load_from_db(self) -> None:
        if not self.db or not hasattr(self.db, "get_ai_agents"):
            return
        for row in self.db.get_ai_agents(limit=500):
            agent = AIAgent(
                agent_id=row["agent_id"],
                name=row["name"],
                owner=row["owner"],
                agent_type=row.get("agent_type", "transformer"),
                status=row.get("status", "active"),
                created_at=row.get("created_at"),
                last_action=row.get("last_action"),
                performance_score=row.get("performance_score", 0),
                total_profit=row.get("total_profit", 0),
                actions_count=row.get("actions_count", 0),
                strategy=row.get("strategy"),
                memory=row.get("memory"),
            )
            self.agents[agent.agent_id] = agent

    def _persist(self, agent: AIAgent) -> None:
        if self.db and hasattr(self.db, "save_ai_agent"):
            self.db.save_ai_agent(agent.to_db())

    def _charge_create_fee(self, owner: str) -> bool:
        if (
            not self.db
            or not hasattr(self.db, "get_balance")
            or not hasattr(self.db, "update_balance")
        ):
            return False
        if self.db.get_balance(owner) < self.CREATE_FEE:
            return False
        self.db.update_balance(owner, -self.CREATE_FEE)
        return True

    def create_agent(self, name: str, owner: str,
                     agent_type: str = "transformer") -> Optional[str]:
        if not name or not owner:
            return None
        if not self._charge_create_fee(owner):
            return None
        agent_id = native.sha256_hex(
            f"{name}{owner}{time.time()}".encode()
        )[:16]
        agent = AIAgent(agent_id, name, owner, agent_type)
        self.agents[agent_id] = agent
        self._persist(agent)
        print(f"[AIAgentManager] Created agent '{name}' ({agent_id}) for {owner[:12]}...")
        return agent_id

    def get_agent(self, agent_id: str) -> Optional[AIAgent]:
        return self.agents.get(agent_id)

    def get_all_agents(self) -> List[Dict]:
        return [a.to_dict() for a in self.agents.values()]

    def get_user_agents(self, owner: str) -> List[Dict]:
        return [a.to_dict() for a in self.agents.values() if a.owner == owner]

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
        if agent.status != "active":
            return {"success": False, "error": "Agent is not active"}
        if amount <= 0 or price <= 0:
            return {"success": False, "error": "Invalid trade parameters"}
        if not self.trade_executor:
            return {"success": False, "error": "Trade execution backend not configured"}
        execution = self.trade_executor({
            "agent_id": agent_id,
            "owner": agent.owner,
            "type": trade_type,
            "amount": amount,
            "price": price,
        })
        if not isinstance(execution, dict) or not execution.get("success"):
            error = execution.get("error", "Trade execution failed") if isinstance(execution, dict) else "Trade execution failed"
            return {"success": False, "error": error}
        result = agent.record_executed_trade(trade_type, amount, price, execution)
        if result.get("success"):
            self._persist(agent)
        return result

    def deactivate(self, agent_id: str) -> bool:
        agent = self.agents.get(agent_id)
        if not agent or agent.status == "inactive":
            return False
        agent.status = "inactive"
        self._persist(agent)
        return True

    def get_stats(self) -> Dict:
        active = sum(1 for a in self.agents.values() if a.status == "active")
        total_profit = sum(a.total_profit for a in self.agents.values())
        return {
            "total_agents": len(self.agents),
            "active_agents": active,
            "total_profit": round(total_profit, 4),
            "total_trades": sum(a.actions_count for a in self.agents.values()),
            "persisted": bool(self.db),
            "create_fee": self.CREATE_FEE,
        }
