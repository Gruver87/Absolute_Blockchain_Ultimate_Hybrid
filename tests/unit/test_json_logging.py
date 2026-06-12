#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты JSON structured logging."""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from observability.logging_setup import JsonFormatter, setup_logging


def test_json_formatter_output():
    fmt = JsonFormatter(node_id="n-test", deployment_mode="staging")
    record = logging.LogRecord(
        name="Node", level=logging.INFO, pathname="", lineno=0,
        msg="block forged", args=(), exc_info=None,
    )
    line = fmt.format(record)
    data = json.loads(line)
    assert data["level"] == "INFO"
    assert data["node_id"] == "n-test"
    assert data["message"] == "block forged"
    assert "ts" in data


def test_setup_logging_json_mode(tmp_path):
    log_file = str(tmp_path / "test.log")
    setup_logging(
        log_level="INFO",
        log_file=log_file,
        log_json=True,
        node_id="n1",
        deployment_mode="dev",
    )
    logging.getLogger("test").info("hello json")
    with open(log_file, encoding="utf-8") as f:
        line = f.readline()
    data = json.loads(line)
    assert data["message"] == "hello json"
