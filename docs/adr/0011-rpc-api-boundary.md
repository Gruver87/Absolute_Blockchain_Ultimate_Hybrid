# ADR 0011 — RPC API Layer (Ports + Isolation)

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Absolute Blockchain maintainers

## Context

JSON-RPC (`JSONRPCHandler`) and REST lived in a monolithic `api/http.py`,
mixing transport with direct `bc.db` / raw store access (ADR 0006 Wave G debt).
WebSocket imported formatters from `api.http`. Body/batch limits existed, but
getLogs amplification and typed param schemas did not.

## Decision

1. **`QueryFacadePort`** — all chain/state reads used by eth_* and Wave-G
   hotspots; enforces max log range/results; never tip UoW.
2. **`RpcPort`** — eth method dispatch + send; JSON-RPC error mapping;
   batch size gate.
3. **Schemas** — frozen dataclasses + codec (no pydantic).
4. **`QueryExecutor`** — bounded thread pool + timeout for heavy reads.
5. **DI:** `Blockchain.attach_query_facade`; `create_rpc_server` wires
   `RpcPort` + query; WS uses `api.eth_format`, not `api.http`.

## Honesty

- ThreadingMixIn retained — ports bound amplification, not “GIL-free RPC”.
- REST feature zoo (NFT/ZK/AI) remains class-attr DI debt.
- Legacy `rpc/server.py` is tests-only.

## Definition of Done

- This ADR present; industrial_gate needles for ADR + `RpcPort` + `QueryFacadePort`
- Ports + Null/Fake + `FakeRpcClient` + ≥20 scenarios
- eth_* reads without `bc.db.get_block_by_hash` / `bc.db.query_evm_logs` in http
- WS does not `from api.http import`
