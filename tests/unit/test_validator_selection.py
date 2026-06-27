#!/usr/bin/env python3
"""Deterministic validator selection invariants."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from consensus.validator_selection import ValidatorSelection


def test_proposer_independent_of_dict_order():
    a = ValidatorSelection(initial_seed="ab" * 32)
    b = ValidatorSelection(initial_seed="ab" * 32)
    validators_a = {"0x03": 10, "0x01": 20, "0x02": 30}
    validators_b = {"0x02": 30, "0x03": 10, "0x01": 20}

    assert a.select_proposer(validators_a, slot=12) == b.select_proposer(validators_b, slot=12)
    assert a.select_proposer_weighted(validators_a, slot=12) == b.select_proposer_weighted(validators_b, slot=12)


def test_shuffle_and_committee_are_deterministic():
    validators = {"0x03": 10, "0x01": 20, "0x02": 30, "0x04": 40}
    a = ValidatorSelection(initial_seed="cd" * 32)
    b = ValidatorSelection(initial_seed="cd" * 32)
    a.set_epoch(7)
    b.set_epoch(7)

    assert list(a.shuffle_validators(validators)) == list(b.shuffle_validators(validators))
    assert a.get_committee(validators, 2) == b.get_committee(validators, 2)


def test_epoch_changes_committee_order():
    validators = {f"0x{i:02x}": i + 1 for i in range(8)}
    selector = ValidatorSelection(initial_seed="ef" * 32)
    selector.set_epoch(1)
    first = selector.get_committee(validators, 4)
    selector.set_epoch(2)
    second = selector.get_committee(validators, 4)

    assert first != second
    assert set(first).issubset(validators)
    assert set(second).issubset(validators)
