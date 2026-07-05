#!/usr/bin/env python3
"""P2P attestation must use the gossiped slot, not the local engine slot."""

from consensus.engine_slashing import ConsensusEngineSlashing


def test_gossip_attestation_uses_remote_slot_not_local():
    """Follower at slot 0 must accept proposer attestation for slot 5."""
    engine = ConsensusEngineSlashing(epoch_size=32)
    engine.add_validator("0xproposer", 5000.0)

    assert engine.on_attestation("0xproposer", "0xblock_a", 5) is True
    assert engine.on_attestation("0xproposer", "0xblock_a", 5) is True
    assert "0xproposer" not in engine.slashing.slashed


def test_gossip_attestation_wrong_local_slot_would_false_slash():
    """Applying remote vote at local slot 0 then slot 5 would false-slash without slot fix."""
    from consensus.slashing import SlashingEngine

    se = SlashingEngine()
    se.register_validator("0xproposer", 100)
    assert se.add_vote("0xproposer", 0, "0xblock_a") is True
    assert se.add_vote("0xproposer", 5, "0xblock_a") is True
    assert not se.is_slashed("0xproposer")
