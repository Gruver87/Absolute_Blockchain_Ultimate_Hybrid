"""Shared ceremony genesis block artifact (leader export → follower import)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

ARTIFACT_VERSION = 1


def resolve_artifact_path(config: Any = None, override: str = "") -> str:
    raw = (
        str(override or "").strip()
        or str(getattr(config, "genesis_artifact_path", "") or "").strip()
        or str(os.environ.get("GENESIS_ARTIFACT_PATH", "") or "").strip()
    )
    return raw


def _block_height(block: Mapping[str, Any]) -> int:
    if "height" in block and block.get("height") is not None:
        return int(block.get("height"))
    if "number" in block and block.get("number") is not None:
        return int(block.get("number"))
    return -1


def load_genesis_block(path: str) -> Optional[Dict[str, Any]]:
    """Load block #0 dict from a shared ceremony/mesh artifact file."""
    p = Path(path)
    if not path or not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[GenesisArtifact] read failed %s: %s", path, exc)
        return None
    if not isinstance(data, Mapping):
        return None
    block = data.get("block") if "block" in data else data
    if not isinstance(block, Mapping):
        return None
    height = _block_height(block)
    if height != 0:
        logger.warning("[GenesisArtifact] refuse non-genesis height=%s", height)
        return None
    if not str(block.get("hash") or "").strip():
        return None
    return dict(block)


def export_genesis_block(
    path: str,
    block: Mapping[str, Any],
    *,
    ceremony_hash: str = "",
    chain_id: int = 0,
    founder_address: str = "",
) -> bool:
    """Atomically write shared genesis artifact for follower boot import."""
    if not path or not isinstance(block, Mapping):
        return False
    if _block_height(block) != 0:
        return False
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": ARTIFACT_VERSION,
            "chain_id": int(chain_id or 0),
            "ceremony_hash": str(ceremony_hash or ""),
            "founder_address": str(founder_address or "").strip().lower(),
            "block": dict(block),
        }
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        tmp.replace(p)
        return True
    except Exception as exc:
        logger.warning("[GenesisArtifact] export failed %s: %s", path, exc)
        try:
            tmp = p.with_suffix(p.suffix + ".tmp")
            if tmp.is_file():
                tmp.unlink()
        except Exception:
            pass
        return False


def load_genesis_artifact(path: str) -> Optional[Dict[str, Any]]:
    """Load full artifact dict ``{block, founder_address, ...}``."""
    p = Path(path)
    if not path or not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[GenesisArtifact] read failed %s: %s", path, exc)
        return None
    if not isinstance(data, Mapping):
        return None
    block = load_genesis_block(path)
    if not block:
        return None
    out = dict(data)
    out["block"] = block
    return out
