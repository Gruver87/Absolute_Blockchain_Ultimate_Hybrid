# core/components — Blockchain facade decomposition
from core.components.ports import (
    ApplyBlockResult,
    StateServicePort,
    TxPipelinePort,
    TxValidationResult,
    ZkGatewayPort,
)
from core.components.state_service import StateService
from core.components.tx_pipeline import TxPipeline
from core.components.zk_gateway import (
    FeaturesZkGateway,
    NullZkGateway,
    build_zk_gateway,
)

__all__ = [
    "ApplyBlockResult",
    "TxValidationResult",
    "TxPipelinePort",
    "StateServicePort",
    "ZkGatewayPort",
    "TxPipeline",
    "StateService",
    "NullZkGateway",
    "FeaturesZkGateway",
    "build_zk_gateway",
]
