# tests/unit/test_bridge_adr0010.py — ADR 0010 ports / validator / FakeEvmBridge (≥20)
"""Industrial isolation scenarios for L1 BridgePort."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from bridge.fake_evm_bridge import FakeEvmBridge, FakeL1Rpc
from bridge.ports import (
    BridgeOpResult,
    InboundEnvelope,
    InboundStatus,
    LockStatus,
    NullBridgePort,
)
from bridge.state_machine import can_transition_lock, normalize_lock_status
from bridge.validators import InboundMessageValidator, compute_replay_key


class _Cfg(SimpleNamespace):
    pass


class _ZkOk:
    def enabled(self):
        return True

    def verify_proof(self, proof, proof_type="knowledge"):
        return bool(proof) and proof.get("valid", False) is True


def _cfg(**kwargs):
    base = dict(
        bridge_enabled=True,
        bridge_mode="fake",
        deployment_mode="dev",
        burn_address="0xburn",
        burn_rate=0.5,
        feature_zk=False,
        bridge_require_inbound_zk=False,
        bridge_require_l1_proof=False,
        bridge_min_confirmations=0,
    )
    base.update(kwargs)
    return _Cfg(**base)


def _env(
    *,
    chain="ethereum",
    to_addr="0xrecv",
    amount=10.0,
    tx="0xabc",
    log_index=0,
    receipt=None,
    zk_proof=None,
):
    return InboundEnvelope(
        from_chain=chain,
        to_addr=to_addr,
        amount=amount,
        event_tx_hash=tx,
        log_index=log_index,
        receipt=receipt,
        zk_proof=zk_proof,
    )


# ── Validator (1–10) ─────────────────────────────────────────────────────────


def test_01_valid_envelope_good_receipt():
    cfg = _cfg(bridge_min_confirmations=1, bridge_require_l1_proof=True)
    l1 = FakeL1Rpc()
    l1.seed_receipt("0xok")
    v = InboundMessageValidator(config=cfg, l1_rpc=l1)
    vr = v.validate(_env(tx="0xok"))
    assert vr.ok
    assert vr.replay_key


def test_02_empty_tx_hash_reject():
    v = InboundMessageValidator(config=_cfg(), l1_rpc=FakeL1Rpc())
    assert not v.validate(_env(tx="")).ok
    assert v.validate(_env(tx="")).reason == "empty_event_tx_hash"


def test_03_bad_amount_reject():
    v = InboundMessageValidator(config=_cfg())
    assert not v.validate(_env(amount=0)).ok
    assert not v.validate(_env(amount=-1)).ok
    bad = _env(amount=float("nan"))
    assert not v.validate(bad).ok


def test_04_insufficient_confirmations_reject():
    cfg = _cfg(bridge_min_confirmations=12, bridge_require_l1_proof=True)
    l1 = FakeL1Rpc()
    l1.seed_receipt("0xslow")
    l1.confirmations["0xslow"] = 2
    v = InboundMessageValidator(config=cfg, l1_rpc=l1)
    vr = v.validate(_env(tx="0xslow"))
    assert not vr.ok
    assert "insufficient_confirmations" in vr.reason


def test_05_receipt_status_failed_reject():
    cfg = _cfg(bridge_require_l1_proof=True)
    l1 = FakeL1Rpc()
    l1.seed_receipt("0xfail", status=0)
    v = InboundMessageValidator(config=cfg, l1_rpc=l1)
    assert v.validate(_env(tx="0xfail")).reason == "receipt_status_failed"


def test_06_receipt_hash_mismatch_reject():
    cfg = _cfg(bridge_require_l1_proof=True)
    l1 = FakeL1Rpc()
    l1.receipts["0xwant"] = {
        "transactionHash": "0xother",
        "status": "0x1",
        "status_int": 1,
        "logs": [{}],
    }
    l1.confirmations["0xwant"] = 12
    v = InboundMessageValidator(config=cfg, l1_rpc=l1)
    assert v.validate(_env(tx="0xwant")).reason == "receipt_hash_mismatch"


def test_07_zk_required_invalid_proof_reject():
    cfg = _cfg(feature_zk=True, bridge_require_inbound_zk=True)
    v = InboundMessageValidator(config=cfg, zk_gateway=_ZkOk())
    vr = v.validate(_env(zk_proof={"valid": False}))
    assert not vr.ok
    assert vr.reason == "zk_proof_invalid"


def test_08_zk_disabled_skips_proof_still_receipt_bound():
    cfg = _cfg(
        feature_zk=False,
        bridge_require_inbound_zk=True,
        bridge_require_l1_proof=True,
    )
    l1 = FakeL1Rpc()
    l1.seed_receipt("0xrecvbound")
    v = InboundMessageValidator(config=cfg, l1_rpc=l1, zk_gateway=_ZkOk())
    # ZK skipped because feature_zk False; receipt still required
    assert v.validate(_env(tx="0xrecvbound")).ok
    assert not v.validate(_env(tx="0xmissing")).ok


def test_09_replay_key_stable():
    a = compute_replay_key("ethereum", "0xTX", 0)
    b = compute_replay_key("Ethereum", "0xTX", 0)
    assert a == b


def test_10_different_log_index_different_key():
    assert compute_replay_key("ethereum", "0xTX", 0) != compute_replay_key(
        "ethereum", "0xTX", 1
    )


# ── BridgePort / state machine (11–19) ───────────────────────────────────────


def test_11_outbound_lock_pending_debit():
    br = FakeEvmBridge(_cfg())
    br.store.balances["0xalice"] = 100.0
    res = br.lock_and_bridge("0xalice", "ethereum", "0xbob", 10.0)
    assert res.ok
    assert res.status == LockStatus.PENDING.value
    assert br.store.balances["0xalice"] < 100.0


def test_12_confirm_lock_confirmed():
    br = FakeEvmBridge(_cfg())
    br.store.balances["0xalice"] = 100.0
    lock = br.lock_and_bridge("0xalice", "ethereum", "0xbob", 10.0)
    txh = lock.detail["tx_hash"]
    conf = br.confirm_lock(txh, "0xl1")
    assert conf.ok and conf.status == LockStatus.CONFIRMED.value


def test_13_refund_pending_credit_back():
    br = FakeEvmBridge(_cfg())
    br.store.balances["0xalice"] = 100.0
    lock = br.lock_and_bridge("0xalice", "ethereum", "0xbob", 10.0)
    before = br.store.balances["0xalice"]
    ref = br.refund(lock.detail["tx_hash"], "test")
    assert ref.ok and ref.status == LockStatus.REFUNDED.value
    assert br.store.balances["0xalice"] > before


def test_14_illegal_confirm_on_refunded():
    br = FakeEvmBridge(_cfg())
    br.store.balances["0xalice"] = 100.0
    lock = br.lock_and_bridge("0xalice", "ethereum", "0xbob", 10.0)
    txh = lock.detail["tx_hash"]
    assert br.refund(txh).ok
    bad = br.confirm_lock(txh, "0xl1")
    assert not bad.ok
    assert not can_transition_lock(normalize_lock_status("refunded"), "confirm_lock")


def test_15_inbound_accepted_credits_once():
    br = FakeEvmBridge(_cfg())
    br.l1.seed_receipt("0xin1")
    res = br.confirm_incoming(_env(tx="0xin1", amount=5.0, to_addr="0xrecv"))
    assert res.ok and res.status == InboundStatus.ACCEPTED.value
    assert br.store.balances["0xrecv"] == pytest.approx(5.0)


def test_16_inbound_duplicate_no_double_balance():
    br = FakeEvmBridge(_cfg())
    br.l1.seed_receipt("0xdup")
    e = _env(tx="0xdup", amount=7.0, to_addr="0xrecv")
    assert br.confirm_incoming(e).status == InboundStatus.ACCEPTED.value
    dup = br.confirm_incoming(e)
    assert dup.ok and dup.status == InboundStatus.DUPLICATE.value
    assert br.store.balances["0xrecv"] == pytest.approx(7.0)


def test_17_inbound_rejected_zk_balance_unchanged():
    cfg = _cfg(feature_zk=True, bridge_require_inbound_zk=True)
    br = FakeEvmBridge(cfg, zk_gateway=_ZkOk())
    br.l1.seed_receipt("0xzkbad")
    before = dict(br.store.balances)
    res = br.confirm_incoming(_env(tx="0xzkbad", zk_proof={"valid": False}))
    assert not res.ok and res.status == InboundStatus.REJECTED.value
    assert br.store.balances == before


def test_18_atomic_abort_mid_claim_no_partial_credit():
    br = FakeEvmBridge(_cfg())
    br.l1.seed_receipt("0xboom")
    br.store.fail_mid_claim = True
    before = dict(br.store.balances)
    res = br.confirm_incoming(_env(tx="0xboom", to_addr="0xrecv", amount=3.0))
    assert not res.ok
    assert "0xrecv" not in br.store.credits or br.store.balances.get("0xrecv", 0) == 0
    assert br.store.balances == before


def test_19_null_bridge_all_ops_disabled():
    nb = NullBridgePort()
    env = _env()
    assert not nb.lock_and_bridge("a", "ethereum", "b", 1).ok
    assert not nb.confirm_incoming(env).ok
    assert not nb.confirm_lock("x", "y").ok
    assert not nb.refund("x").ok
    assert nb.get_stats()["enabled"] is False


# ── FakeEvmBridge / integration (20–25) ──────────────────────────────────────


def test_20_forged_receipt_refused():
    cfg = _cfg(bridge_require_l1_proof=True)
    br = FakeEvmBridge(cfg)
    br.l1.seed_receipt("0xforge")
    br.l1.forge_status_failed = True
    res = br.confirm_incoming(_env(tx="0xforge"))
    assert not res.ok
    assert res.status == InboundStatus.REJECTED.value


def test_21_confirmation_delay_then_success():
    cfg = _cfg(bridge_min_confirmations=3, bridge_require_l1_proof=True)
    br = FakeEvmBridge(cfg)
    br.l1.seed_receipt("0xdelay")
    br.l1.delay_confirmations_target = 3
    br.l1.confirmations["0xdelay"] = 12
    e = _env(tx="0xdelay")
    assert not br.confirm_incoming(e).ok
    assert not br.confirm_incoming(e).ok
    ok = br.confirm_incoming(e)
    assert ok.ok and ok.status == InboundStatus.ACCEPTED.value


def test_22_contract_revert_outbound_refund_path():
    br = FakeEvmBridge(_cfg())
    br.store.balances["0xalice"] = 50.0
    br.contract_revert = True
    res = br.lock_and_bridge("0xalice", "ethereum", "0xbob", 5.0)
    assert not res.ok
    assert br.store.balances["0xalice"] == pytest.approx(50.0)


def test_23_zk_delay_then_fail_no_credit():
    br = FakeEvmBridge(_cfg(feature_zk=True, bridge_require_inbound_zk=True), zk_gateway=_ZkOk())
    br.l1.seed_receipt("0xzkd")
    br.zk_fail = True
    br.zk_delay_ms = 1
    before = dict(br.store.balances)
    res = br.confirm_incoming(_env(tx="0xzkd", zk_proof={"valid": True}))
    assert not res.ok
    assert br.store.balances == before


def test_24_oracle_duplicate_submission_duplicate():
    br = FakeEvmBridge(_cfg())
    br.l1.seed_receipt("0xoracle")
    e = _env(tx="0xoracle", amount=2.0)
    assert br.confirm_incoming(e).status == InboundStatus.ACCEPTED.value
    assert br.confirm_incoming(e).status == InboundStatus.DUPLICATE.value


def test_25_prod_policy_refuses_outbound_without_l1_tx_hash():
    br = FakeEvmBridge(_cfg(deployment_mode="prod"))
    br.store.balances["0xalice"] = 100.0
    res = br.lock_and_bridge("0xalice", "ethereum", "0xbob", 10.0)
    assert not res.ok
    assert "l1_tx_hash" in str(res.detail.get("error", ""))


def test_attach_bridge_on_blockchain_facade(tmp_path):
    from core.blockchain import Blockchain
    from runtime.config import Config
    from storage.database import Database
    from storage.factory import open_storage

    cfg = Config()
    cfg.db_path = str(tmp_path / "adr0010.db")
    cfg.data_dir = str(tmp_path)
    db = Database(cfg.db_path)
    storage = open_storage(db, repair_on_open=False)
    bc = Blockchain(cfg, db=db, storage=storage)
    assert isinstance(bc.bridge, NullBridgePort)
    fake = FakeEvmBridge(_cfg())
    bc.attach_bridge(fake)
    assert bc.bridge is fake


def test_bridge_op_result_legacy_dict():
    r = BridgeOpResult(
        ok=True,
        status=InboundStatus.DUPLICATE.value,
        detail={"credit_key": "abc"},
    )
    d = r.as_legacy_dict()
    assert d["duplicate"] is True
    assert d["confirmed"] is True
