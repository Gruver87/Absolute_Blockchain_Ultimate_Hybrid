#!/usr/bin/env python3
"""Production API: direct /contract/deploy must be rejected (mempool only)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.http import _reject_direct_deploy_in_prod
from runtime.config import Config


def test_prod_rejects_direct_contract_deploy():
    cfg = Config()
    cfg.deployment_mode = "prod"
    with pytest.raises(ValueError, match="via_mempool"):
        _reject_direct_deploy_in_prod(cfg, via_mempool=False)


def test_prod_allows_mempool_deploy_flag():
    cfg = Config()
    cfg.deployment_mode = "prod"
    _reject_direct_deploy_in_prod(cfg, via_mempool=True)


def test_dev_allows_direct_deploy():
    cfg = Config()
    cfg.deployment_mode = "dev"
    _reject_direct_deploy_in_prod(cfg, via_mempool=False)
