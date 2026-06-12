#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structured logging для промышленного профиля."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional


class JsonFormatter(logging.Formatter):
    """Одна строка JSON на запись — для Loki / ELK / CloudWatch."""

    def __init__(self, node_id: str = "node-1", deployment_mode: str = "dev"):
        super().__init__()
        self.node_id = node_id
        self.deployment_mode = deployment_mode

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "node_id": self.node_id,
            "deployment_mode": self.deployment_mode,
        }
        if record.exc_info and record.exc_info[1]:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(
    *,
    log_level: str = "INFO",
    log_file: str = "data/node.log",
    log_json: bool = False,
    node_id: str = "node-1",
    deployment_mode: str = "dev",
) -> None:
    import os

    level = getattr(logging, log_level.upper(), logging.INFO)
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    if log_json:
        formatter = JsonFormatter(node_id=node_id, deployment_mode=deployment_mode)
    else:
        formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    for stream in (sys.stdout,):
        sh = logging.StreamHandler(stream)
        sh.setFormatter(formatter)
        root.addHandler(sh)

    try:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except OSError as e:
        logging.getLogger("Node").warning("File logging disabled: %s", e)
