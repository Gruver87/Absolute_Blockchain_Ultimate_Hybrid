# api/rpc_schema.py — ADR 0011 JSON-RPC request codec + typed param DTOs
"""Decode/validate JSON-RPC envelopes without pydantic — no raw dict params into domain."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from api.ports import RpcRequest, RpcResponse

_METHOD_RE = re.compile(r"^[a-zA-Z0-9_/\.]{1,128}$")
_HEX_BODY_RE = re.compile(r"^[0-9a-fA-F]+$")


def rpc_error(code: int, message: str, rid: Any = None) -> RpcResponse:
    return RpcResponse(
        ok=False, id=rid, error={"code": int(code), "message": str(message)}
    )


# ── Per-method param DTOs (strict) ───────────────────────────────────────────


@dataclass(frozen=True)
class GetBlockByNumberParams:
    tag: str
    full_tx: bool = False


@dataclass(frozen=True)
class GetBlockByHashParams:
    block_hash: str
    full_tx: bool = False


@dataclass(frozen=True)
class GetBalanceParams:
    address: str
    block_tag: str = "latest"


@dataclass(frozen=True)
class AddressOnlyParams:
    address: str


@dataclass(frozen=True)
class TxHashParams:
    tx_hash: str


@dataclass(frozen=True)
class SendRawTxParams:
    raw_tx: str


@dataclass(frozen=True)
class GetStorageAtParams:
    address: str
    slot: str


@dataclass(frozen=True)
class GetLogsParams:
    from_block: str = "0x0"
    to_block: str = "latest"
    address: Optional[Union[str, Tuple[str, ...]]] = None
    topics: Tuple[Any, ...] = ()
    limit: int = 1000


@dataclass(frozen=True)
class DecodedRpcCall:
    """Fully decoded call: envelope + typed params (or None for no-param methods)."""

    request: RpcRequest
    params_dto: Any = None


def _is_hex_string(value: Any, *, exact_body_len: Optional[int] = None) -> bool:
    if not isinstance(value, str) or not value.startswith("0x"):
        return False
    body = value[2:]
    if exact_body_len is not None and len(body) != exact_body_len:
        return False
    if not body:
        return exact_body_len in (None, 0)
    return bool(_HEX_BODY_RE.match(body))


def _require_address(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def parse_method_params(method: str, params: tuple) -> Tuple[Optional[Any], Optional[str]]:
    """
    Return (dto, error_message).
    error_message set → caller maps to JSON-RPC -32602.
    """
    if method in ("eth_blockNumber", "eth_chainId", "net_version", "web3_clientVersion",
                  "net_peerCount", "eth_mining", "eth_syncing", "eth_gasPrice",
                  "eth_maxPriorityFeePerGas", "eth_accounts", "eth_coinbase",
                  "eth_hashrate", "eth_protocolVersion", "eth_getMempoolSize"):
        if len(params) > 0:
            # tolerate extra ignored params for eth_blockNumber etc. (wallet compat)
            pass
        return None, None

    if method == "eth_getBlockByNumber":
        if len(params) < 1:
            return None, "eth_getBlockByNumber expects block tag"
        tag = params[0]
        if not isinstance(tag, str):
            return None, "block tag must be string"
        full_tx = bool(params[1]) if len(params) > 1 else False
        return GetBlockByNumberParams(tag=tag, full_tx=full_tx), None

    if method == "eth_getBlockByHash":
        if len(params) < 1:
            return None, "block hash required"
        h = params[0]
        if not _is_hex_string(h, exact_body_len=64):
            return None, "non-hex block hash"
        full_tx = bool(params[1]) if len(params) > 1 else False
        return GetBlockByHashParams(block_hash=str(h), full_tx=full_tx), None

    if method == "eth_getBalance":
        if len(params) < 1:
            return None, "eth_getBalance expects address"
        addr = _require_address(params[0])
        if not addr:
            return None, "invalid address"
        tag = str(params[1]) if len(params) > 1 else "latest"
        return GetBalanceParams(address=addr, block_tag=tag), None

    if method in ("eth_getTransactionCount", "eth_getCode"):
        if len(params) < 1:
            return None, f"{method} expects address"
        addr = _require_address(params[0])
        if not addr:
            return None, "invalid address"
        return AddressOnlyParams(address=addr), None

    if method in ("eth_getTransactionByHash", "eth_getTransactionReceipt"):
        if len(params) < 1:
            return None, "tx hash required"
        h = params[0]
        if not isinstance(h, str) or not h:
            return None, "invalid tx hash"
        return TxHashParams(tx_hash=h), None

    if method == "eth_sendRawTransaction":
        if len(params) < 1:
            return None, "raw tx required"
        raw = params[0]
        if not isinstance(raw, str) or not raw:
            return None, "raw tx must be hex string"
        return SendRawTxParams(raw_tx=raw), None

    if method == "eth_getStorageAt":
        if len(params) < 2:
            return None, "eth_getStorageAt expects address and slot"
        addr = _require_address(params[0])
        if not addr:
            return None, "invalid address"
        slot = params[1]
        if not isinstance(slot, str):
            return None, "slot must be string"
        return GetStorageAtParams(address=addr, slot=slot), None

    if method == "eth_getLogs":
        if len(params) < 1 or not isinstance(params[0], dict):
            return None, "eth_getLogs expects object filter"
        filt = params[0]
        address = filt.get("address")
        addr_norm: Optional[Union[str, Tuple[str, ...]]] = None
        if isinstance(address, list):
            addr_norm = tuple(str(a) for a in address)
        elif isinstance(address, str):
            addr_norm = address
        topics = filt.get("topics") or []
        if not isinstance(topics, list):
            return None, "topics must be array"
        try:
            limit = int(filt.get("limit") or 1000)
        except (TypeError, ValueError):
            return None, "invalid limit"
        return GetLogsParams(
            from_block=str(filt.get("fromBlock", "0x0")),
            to_block=str(filt.get("toBlock", "latest")),
            address=addr_norm,
            topics=tuple(topics),
            limit=limit,
        ), None

    if method in (
        "eth_getBlockTransactionCountByHash",
        "eth_getUncleCountByBlockHash",
    ):
        err = validate_block_hash_param(params)
        if err:
            return None, err
        return GetBlockByHashParams(block_hash=str(params[0]), full_tx=False), None

    # Remaining methods keep tuple params; arity checked in RpcService
    return None, None


def decode_rpc_payload(
    raw: Any, *, max_batch: int = 32
) -> Union[RpcRequest, List[Union[RpcRequest, RpcResponse]], RpcResponse]:
    """Decode already-parsed JSON into RpcRequest(s) or an error response."""
    if raw is None or raw == "":
        return rpc_error(-32600, "empty request")
    if isinstance(raw, list):
        if len(raw) == 0:
            return rpc_error(-32600, "empty batch")
        if len(raw) > int(max_batch):
            return rpc_error(-32600, f"batch too large (max {max_batch})")
        out: List[Union[RpcRequest, RpcResponse]] = []
        for item in raw:
            out.append(decode_single_request(item))
        return out
    return decode_single_request(raw)


def decode_single_request(raw: Any) -> Union[RpcRequest, RpcResponse]:
    if not isinstance(raw, dict):
        return rpc_error(-32600, "Invalid Request")
    rid = raw.get("id")
    version = str(raw.get("jsonrpc", "") or "")
    if "jsonrpc" in raw and version != "2.0":
        return rpc_error(-32600, "Invalid Request: jsonrpc must be 2.0", rid)
    method = raw.get("method", "")
    if not isinstance(method, str) or not method:
        return rpc_error(-32600, "Invalid Request: method required", rid)
    if len(method) > 128 or not _METHOD_RE.match(method):
        return rpc_error(-32600, "Invalid Request: method rejected", rid)
    params = raw.get("params", [])
    if params is None:
        params = []
    if not isinstance(params, (list, tuple)):
        return rpc_error(-32602, "Invalid params: must be array", rid)
    return RpcRequest(
        method=method,
        params=tuple(params),
        id=rid,
        jsonrpc="2.0",
    )


def decode_and_validate(
    raw: Any, *, max_batch: int = 32
) -> Union[DecodedRpcCall, List[Union[DecodedRpcCall, RpcResponse]], RpcResponse]:
    """Full pipeline: envelope decode + typed param DTO."""
    decoded = decode_rpc_payload(raw, max_batch=max_batch)
    if isinstance(decoded, RpcResponse):
        return decoded
    if isinstance(decoded, list):
        out: List[Union[DecodedRpcCall, RpcResponse]] = []
        for item in decoded:
            if isinstance(item, RpcResponse):
                out.append(item)
                continue
            dto, err = parse_method_params(item.method, item.params)
            if err:
                out.append(rpc_error(-32602, err, item.id))
            else:
                out.append(DecodedRpcCall(request=item, params_dto=dto))
        return out
    dto, err = parse_method_params(decoded.method, decoded.params)
    if err:
        return rpc_error(-32602, err, decoded.id)
    return DecodedRpcCall(request=decoded, params_dto=dto)


def validate_get_balance_params(params: tuple) -> Optional[str]:
    _, err = parse_method_params("eth_getBalance", params)
    return err


def validate_block_hash_param(params: tuple) -> Optional[str]:
    if len(params) < 1:
        return "block hash required"
    h = params[0]
    if not _is_hex_string(h, exact_body_len=64):
        return "non-hex block hash"
    return None
