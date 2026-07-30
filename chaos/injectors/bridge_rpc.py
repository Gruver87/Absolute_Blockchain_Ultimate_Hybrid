# chaos/injectors/bridge_rpc.py — bad claims + bad JSON-RPC batches (ADR 0012)
"""Bombard BridgePort + RpcPort fakes with forged receipts and malformed batches."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from chaos.ports import (
    FaultKind,
    InjectionOutcome,
    InjectionResult,
    InjectionSpec,
)


class BridgeRpcChaosInjector:
    KIND_MAP = {FaultKind.BRIDGE_BAD_CLAIM, FaultKind.RPC_BAD_BATCH}

    def __init__(self) -> None:
        self._armed: Optional[InjectionSpec] = None
        self._bridge = None
        self._rpc = None

    def arm(self, spec: InjectionSpec) -> None:
        self._armed = spec

    def disarm(self) -> None:
        self._armed = None

    def fire(self, spec: InjectionSpec) -> InjectionResult:
        try:
            if spec.kind == FaultKind.BRIDGE_BAD_CLAIM:
                return self._bad_claim(spec)
            if spec.kind == FaultKind.RPC_BAD_BATCH:
                return self._bad_batch(spec)
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail="unsupported_kind",
            )
        except Exception as exc:
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail=f"uncaught:{exc!r}",
            )

    def _bad_claim(self, spec: InjectionSpec) -> InjectionResult:
        from bridge.fake_evm_bridge import FakeEvmBridge
        from bridge.ports import InboundEnvelope, InboundStatus

        cfg = SimpleNamespace(
            bridge_enabled=True,
            bridge_mode="fake",
            deployment_mode="dev",
            burn_address="0xburn",
            burn_rate=0.5,
            feature_zk=False,
            bridge_require_inbound_zk=False,
            bridge_require_l1_proof=True,
            bridge_min_confirmations=1,
        )
        br = FakeEvmBridge(cfg)
        self._bridge = br
        # Missing receipt → reject, no credit
        env = InboundEnvelope(
            from_chain="ethereum",
            to_addr="0xrecv",
            amount=5.0,
            event_tx_hash="0x" + "ab" * 32,
            log_index=0,
        )
        before = dict(br.store.balances)
        res = br.confirm_incoming(env)
        if res.status == InboundStatus.REJECTED.value and br.store.balances == before:
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.FAIL_CLOSED.value,
                detail=str(res.detail.get("reason") or res.detail.get("error") or "rejected"),
            )
        if res.ok and res.status != InboundStatus.REJECTED.value:
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail="bad_claim_credited",
            )
        return InjectionResult(
            kind=spec.kind,
            outcome=InjectionOutcome.FAIL_CLOSED.value,
            detail="rejected",
        )

    def _bad_batch(self, spec: InjectionSpec) -> InjectionResult:
        from api.fake_rpc import FakeRpcClient

        cfg = SimpleNamespace(
            jsonrpc_max_batch=4,
            chain_id=77777,
            node_version="chaos",
            gas_price_wei=1e-9,
            mining_enabled=False,
            deployment_mode="dev",
            miner_address="",
            rpc_get_logs_max_range=100,
            rpc_get_logs_max_results=10,
            rpc_heavy_query_timeout_ms=50,
            rpc_heavy_workers=1,
            rpc_full_tx_block_max_txs=10,
        )
        client = FakeRpcClient(config=cfg)
        self._rpc = client
        mode = str(spec.params.get("mode") or "oversized")
        if mode == "malformed":
            out = client.handle_raw(b"{not-json")
            if isinstance(out, dict) and out.get("error", {}).get("code") == -32700:
                return InjectionResult(
                    kind=spec.kind,
                    outcome=InjectionOutcome.FAIL_CLOSED.value,
                    detail="parse_error",
                )
        elif mode == "bad_params":
            out = client.call("eth_getBalance", [])
            if isinstance(out, dict) and out.get("error", {}).get("code") == -32602:
                return InjectionResult(
                    kind=spec.kind,
                    outcome=InjectionOutcome.FAIL_CLOSED.value,
                    detail="invalid_params",
                )
        else:
            batch = [
                {"jsonrpc": "2.0", "id": i, "method": "eth_blockNumber", "params": []}
                for i in range(20)
            ]
            out = client.handle_raw(batch)
            if isinstance(out, dict) and out.get("error", {}).get("code") == -32600:
                return InjectionResult(
                    kind=spec.kind,
                    outcome=InjectionOutcome.FAIL_CLOSED.value,
                    detail="batch_too_large",
                )
        return InjectionResult(
            kind=spec.kind,
            outcome=InjectionOutcome.PANIC.value,
            detail=f"unexpected:{out!r}"[:200],
        )
