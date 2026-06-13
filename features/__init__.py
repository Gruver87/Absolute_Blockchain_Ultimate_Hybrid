"""Feature availability flags for API gating and /features endpoint."""
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional


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
        )

    def to_api_dict(self, instances: Optional[Dict[str, Any]] = None) -> Dict:
        instances = instances or {}
        out = {}
        for name, enabled in asdict(self).items():
            live = instances.get(name)
            out[name] = {
                "enabled": bool(enabled and live is not None),
                "configured": enabled,
                "loaded": live is not None,
            }
        return out
