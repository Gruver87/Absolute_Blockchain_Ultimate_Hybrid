# chaos/__init__.py — ADR 0012 Chaos Injection Framework
"""Lab/test-only total chaos bombardment — never arm from prod NodeOrchestrator."""

from chaos.engine import TotalChaosEngine, build_default_chaos_stack, refuse_prod_arming
from chaos.ports import (
    ChaosReport,
    FaultFamily,
    FaultKind,
    InjectionOutcome,
    InjectionResult,
    InjectionSpec,
)

__all__ = [
    "TotalChaosEngine",
    "build_default_chaos_stack",
    "refuse_prod_arming",
    "FaultKind",
    "FaultFamily",
    "InjectionSpec",
    "InjectionResult",
    "InjectionOutcome",
    "ChaosReport",
]
