from consensus.engine_slashing import ConsensusEngineSlashing
from consensus.slashing import SlashingEngine


def test_solo_validator_many_blocks_not_slashed():
    """One validator attesting each new block must not trigger epoch-based false slash."""
    engine = ConsensusEngineSlashing(epoch_size=32)
    engine.add_validator("0xvalidator1", 1000)

    for slot in range(20):
        ok = engine.on_attestation("0xvalidator1", f"0xblock{slot:04d}", slot)
        assert ok is True

    assert "0xvalidator1" not in engine.slashing.slashed


def test_double_vote_same_slot_still_slashes():
    se = SlashingEngine()
    se.register_validator("v1", 100)
    assert se.add_vote("v1", 5, "0xaaa") is True
    assert se.add_vote("v1", 5, "0xbbb") is False
    assert se.is_slashed("v1")


def test_different_slots_same_epoch_allowed():
    se = SlashingEngine()
    se.register_validator("v1", 100)
    assert se.add_vote("v1", 0, "0xblock0") is True
    assert se.add_vote("v1", 1, "0xblock1") is True
    assert not se.is_slashed("v1")
