"""Feature availability flags for API gating and /features endpoint."""
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

# production = affects L1 state; routing = logical layer on L1; dev-test/r-and-d = blocked in prod
MODULE_TIERS: Dict[str, str] = {
    "evm": "production",
    "bridge": "production",
    "mempool": "production",
    "p2p": "production",
    "consensus": "production",
    "sharding": "routing",
    "oracles": "offchain",
    "nft": "production",
    "wasm": "r-and-d",
    "plasma": "dev-test",
    "lightning": "dev-test",
    "zk": "r-and-d",
    "pq": "r-and-d",
    "mev": "analysis",
    "ai_agents": "dev-test",
    "reorg_predictor": "production",
    "cross_bridge": "dev-test",
}


@dataclass
class FeatureFlags:
    evm: bool = True
    bridge: bool = True
    nft: bool = True
    zk: bool = True
    sharding: bool = True
    oracles: bool = True
    wasm: bool = True
    plasma: bool = True
    lightning: bool = True
    pq: bool = True
    mev: bool = True
    ai_agents: bool = True

    @classmethod
    def from_config(cls, config) -> "FeatureFlags":
        return cls(
            evm=getattr(config, "evm_enabled", True),
            bridge=getattr(config, "bridge_enabled", True),
            nft=getattr(config, "feature_nft", True),
            zk=getattr(config, "feature_zk", True),
            sharding=getattr(config, "feature_sharding", True),
            oracles=getattr(config, "feature_oracles", True),
            wasm=getattr(config, "feature_wasm", True),
            plasma=getattr(config, "feature_plasma", True),
            lightning=getattr(config, "feature_lightning", True),
            pq=getattr(config, "feature_pq", True),
            mev=getattr(config, "feature_mev", True),
            ai_agents=getattr(config, "feature_ai_agents", True),
        )

    def to_api_dict(self, instances: Optional[Dict[str, Any]] = None, config=None) -> Dict:
        instances = instances or {}
        is_prod = getattr(config, "is_production", False) if config else False
        out = {"deployment_mode": getattr(config, "deployment_mode", "dev") if config else "dev"}
        for name, enabled in asdict(self).items():
            live = instances.get(name)
            tier = MODULE_TIERS.get(name, "dev-test")
            blocked_in_prod = is_prod and tier in (
                "dev-test", "r-and-d", "offchain", "routing", "analysis"
            )
            out[name] = {
                "enabled": bool(enabled and live is not None and not blocked_in_prod),
                "configured": enabled,
                "loaded": live is not None,
                "tier": tier,
                "dev_only": tier in ("dev-test", "r-and-d", "offchain"),
                "analysis": tier == "analysis",
                "prod_blocked_reason": (
                    f"{tier} feature is not production-grade"
                    if blocked_in_prod
                    else ""
                ),
            }
        return out


def probe_optional_module(module_path: str, class_name: str) -> Dict[str, Any]:
    """Honest import probe for optional R&D modules (wasm, plasma, etc.)."""
    try:
        import importlib

        mod = importlib.import_module(module_path)
        getattr(mod, class_name)
        return {"module_importable": True, "import_error": None}
    except Exception as exc:
        return {"module_importable": False, "import_error": str(exc)}


OPTIONAL_MODULE_PROBES: Dict[str, tuple[str, str]] = {
    "wasm": ("features.wasm_vm", "WASMVirtualMachine"),
    "plasma": ("features.plasma", "PlasmaChain"),
    "lightning": ("features.lightning", "LightningNetwork"),
    "zk": ("features.zk", "ZKProofSystem"),
    "ai_agents": ("features.ai_manager", "AIAgentManager"),
    "mev": ("features.mev_analyzer", "MEVAnalyzer"),
    "pq": ("features.postquantum", "PostQuantumManager"),
}
