"""
L1 JSON-RPC helpers for bridge relayer (Ethereum-compatible chains).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional


_L1_RPC_ENV_KEYS = ("ETH_RPC_URL", "BSC_RPC_URL", "POLYGON_RPC_URL")
_PLACEHOLDER_RPC = re.compile(
    r"(?i)(ваш-ethereum|your-ethereum|your-mainnet|changeme|placeholder|todo|rpc\.example$|example\.com$)"
)


def is_placeholder_l1_rpc_url(url: str) -> bool:
    from runtime.secret_utils import is_placeholder_secret

    url = (url or "").strip()
    if not url:
        return True
    if is_placeholder_secret(url):
        return True
    return bool(_PLACEHOLDER_RPC.search(url))


def configured_l1_rpc_urls() -> Dict[str, str]:
    """Non-empty L1 RPC URLs from environment (env key -> URL)."""
    out: Dict[str, str] = {}
    for key in _L1_RPC_ENV_KEYS:
        url = os.environ.get(key, "").strip()
        if url:
            out[key] = url
    return out


def probe_l1_rpc_url(rpc_url: str, timeout: float = 5.0) -> Dict[str, Any]:
    """Lightweight eth_blockNumber probe for startup / config validation."""
    if not rpc_url:
        return {"ok": False, "error": "empty rpc url", "url": rpc_url}
    try:
        result = _rpc_call(rpc_url, "eth_blockNumber", [], timeout=timeout)
        block = _parse_hex_int(result)
        if block <= 0:
            return {
                "ok": False,
                "error": f"unexpected block number {block}",
                "url": rpc_url,
            }
        return {"ok": True, "url": rpc_url, "block_number": block}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "url": rpc_url}


def probe_configured_l1_rpcs(timeout: float = 5.0) -> Dict[str, Any]:
    """Probe every configured L1 RPC URL; succeeds only if all respond."""
    urls = configured_l1_rpc_urls()
    if not urls:
        return {"ok": False, "error": "no L1 RPC URLs configured", "probes": {}}
    probes = {key: probe_l1_rpc_url(url, timeout=timeout) for key, url in urls.items()}
    failed = [key for key, probe in probes.items() if not probe.get("ok")]
    ok = not failed
    err = None
    if not ok:
        err = "; ".join(f"{key}: {probes[key].get('error')}" for key in failed)
    return {"ok": ok, "error": err, "probes": probes}


def chain_rpc_url(chain: str) -> str:
    """Resolve RPC URL from env: ETH_RPC_URL, POLYGON_RPC_URL, etc."""
    aliases = {
        "ethereum": "ETH",
        "eth": "ETH",
        "bsc": "BSC",
        "binance": "BSC",
        "polygon": "POLYGON",
        "matic": "POLYGON",
    }
    norm = chain.lower().replace("-", "_")
    prefix = aliases.get(norm, norm.upper())
    key = f"{prefix}_RPC_URL"
    return os.environ.get(key, "").strip()


def min_confirmations() -> int:
    raw = os.environ.get("BRIDGE_MIN_CONFIRMATIONS", "12")
    try:
        return max(1, int(raw))
    except ValueError:
        return 12


def _ascii_request_url(url: str) -> str:
    """Percent-encode non-ASCII host/path so urllib accepts the URL."""
    parts = urllib.parse.urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        return url
    host = parts.hostname or ""
    if host:
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            host = urllib.parse.quote(host, safe="")
    port = f":{parts.port}" if parts.port else ""
    netloc = host + port
    if parts.username:
        userinfo = parts.username
        if parts.password:
            userinfo = f"{userinfo}:{parts.password}"
        netloc = f"{userinfo}@{netloc}"
    return urllib.parse.urlunsplit(
        (parts.scheme, netloc, parts.path, parts.query, parts.fragment)
    )


def _rpc_call(rpc_url: str, method: str, params: list, timeout: float = 15) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(
        _ascii_request_url(rpc_url),
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("result")


def _parse_hex_int(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    s = str(value)
    return int(s, 16) if s.startswith("0x") else int(s)


def get_block_number(rpc_url: str) -> int:
    result = _rpc_call(rpc_url, "eth_blockNumber", [])
    return _parse_hex_int(result)

def get_contract_code(
    rpc_url: str,
    address: str,
    *,
    timeout: float = 10.0,
    fail_closed: bool = True,
) -> str:
    """Return EVM bytecode at address (eth_getCode).

    On RPC failure: raise RuntimeError when fail_closed (default), else return \"0x\".
    Missing url/address returns \"0x\" (not deployed / not configured).
    """
    if not rpc_url or not address:
        return "0x"
    try:
        result = _rpc_call(rpc_url, "eth_getCode", [address, "latest"], timeout=timeout)
        return str(result or "0x")
    except Exception as exc:
        if fail_closed:
            raise RuntimeError(f"eth_getCode failed for {address}: {exc}") from exc
        return "0x"


def get_tx_confirmations(rpc_url: str, tx_hash: str) -> Optional[int]:
    """
    Return confirmation count for a mined successful tx, or None if not found / RPC error.

    Fail-closed: receipt must include status=0x1 (success). Failed or status-less
    receipts do not count as confirmed.
    """
    if not rpc_url or not tx_hash:
        return None
    try:
        receipt = _rpc_call(rpc_url, "eth_getTransactionReceipt", [tx_hash])
        if not receipt:
            return 0
        if not _receipt_status_ok(receipt):
            return 0
        block_num = _parse_hex_int(receipt.get("blockNumber"))
        if block_num <= 0:
            return 0
        head = get_block_number(rpc_url)
        return max(0, head - block_num + 1)
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, ValueError, TimeoutError):
        return None


def _receipt_status_ok(receipt: dict) -> bool:
    """True only when eth_getTransactionReceipt reports successful execution."""
    status = receipt.get("status")
    if status is None:
        # Pre-Byzantium / incomplete mocks — do not invent success.
        return False
    try:
        if isinstance(status, str):
            value = int(status, 16) if status.startswith("0x") else int(status)
        else:
            value = int(status)
    except (TypeError, ValueError):
        return False
    return value == 1


def is_tx_confirmed(rpc_url: str, tx_hash: str, required: Optional[int] = None) -> bool:
    need = required if required is not None else min_confirmations()
    conf = get_tx_confirmations(rpc_url, tx_hash)
    return conf is not None and conf >= need


def load_l1_queue(path: str) -> Dict[str, list]:
    if not path or not os.path.isfile(path):
        return {"outbound": [], "incoming": []}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "outbound": list(data.get("outbound", [])),
        "incoming": list(data.get("incoming", [])),
    }


def save_l1_queue(path: str, queue: Dict[str, list]) -> None:
    """Atomically persist L1 queue JSON (temp file + replace)."""
    import tempfile

    abs_path = os.path.abspath(path)
    os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
    payload = json.dumps(queue, indent=2)
    fd, tmp = tempfile.mkstemp(
        prefix=".l1_queue_",
        suffix=".tmp",
        dir=os.path.dirname(abs_path) or ".",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, abs_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

