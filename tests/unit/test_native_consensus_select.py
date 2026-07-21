#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rust-backed consensus proposer/committee and state-engine root parity."""

import json

import pytest

from consensus.validator_selection import ValidatorSelection
from consensus_engine import ConsensusEngine
from crypto import native
from execution.state_root import compute_state_engine_root


def _validator_payload():
    return {
        "0x03": 10,
        "0x01": 20,
        "0x02": 30,
        "0x04": 40,
    }


def test_consensus_stake_weighted_proposer_matches_engine():
    engine = ConsensusEngine()
    for addr, stake in (("0x01", 100.0), ("0x02", 200.0), ("0x03", 50.0)):
        engine.add_validator(addr, stake)
    engine.current_epoch = 3
    engine.current_slot = 7

    via_engine = engine.select_proposer()
    payload = [(v.address, v.stake, v.is_active) for v in engine.validators.values()]
    via_native = native.consensus_stake_weighted_proposer(payload, 3, 7)
    assert via_engine is not None
    assert via_engine.address == via_native


def test_consensus_fisher_yates_committee_matches_engine():
    engine = ConsensusEngine()
    for i in range(8):
        engine.add_validator(f"0x{i:02x}", float(10 + i))

    for slot in (0, 4, 9):
        committee_size = max(1, len(engine.validators) // 32)
        payload = [(v.address, v.stake, v.is_active) for v in engine.validators.values()]
        native_addrs = native.consensus_fisher_yates_committee(payload, slot, committee_size)
        engine_addrs = [v.address for v in engine.get_committee(slot)]
        assert native_addrs == engine_addrs


def test_validator_selection_native_matches_python_contract():
    seed = "ab" * 32
    epoch = 7
    slot = 12
    validators = _validator_payload()
    rows = [(addr, int(stake)) for addr, stake in validators.items()]

    selector = ValidatorSelection(initial_seed=seed)
    selector.set_epoch(epoch)

    assert native.validator_selection_proposer(seed, epoch, slot, rows) == selector.select_proposer(
        validators, slot
    )
    assert native.validator_selection_proposer_weighted(seed, epoch, slot, rows) == (
        selector.select_proposer_weighted(validators, slot)
    )
    assert native.validator_selection_committee(seed, epoch, rows, 2) == selector.get_committee(
        validators, 2
    )
    assert dict(native.validator_selection_shuffle(seed, epoch, rows)) == selector.shuffle_validators(
        validators
    )


def test_state_engine_root_matches_native_json_kernel():
    class _Acc:
        def __init__(self, balance: int, nonce: int):
            self.balance = balance
            self.nonce = nonce

    accounts = {
        "0x01": _Acc(1_500_000, 2),
        "0x02": _Acc(0, 0),
    }
    payload = {
        addr: {"balance_satoshi": int(acc.balance), "nonce": int(acc.nonce)}
        for addr, acc in accounts.items()
    }
    encoded = json.dumps(payload, sort_keys=True)
    assert compute_state_engine_root(accounts) == native.state_engine_root_from_accounts_json(encoded)


def test_native_consensus_rejects_too_many_validators():
    if not native.native_available():
        return
    import abs_native

    huge = [("0x01", 1.0, True)] * 10_001
    with pytest.raises(ValueError, match="too_many_validators"):
        abs_native.consensus_stake_weighted_proposer(huge, 0, 0)
