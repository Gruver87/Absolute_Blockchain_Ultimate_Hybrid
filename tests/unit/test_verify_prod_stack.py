#!/usr/bin/env python3
"""verify_prod_stack.py tests."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_prod_stack


def test_verify_prod_stack_static_ok():
    with patch.object(verify_prod_stack, "check_prod_gate", return_value=[]):
        with patch.object(verify_prod_stack, "check_docker_prod_compose", return_value=[]):
            errors = verify_prod_stack.check_config_validate()
    assert isinstance(errors, list)


def test_docker_compose_prod_has_relayer():
    text = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "relayer:" in text
    assert "profiles:" in text
    assert "- bridge" in text
