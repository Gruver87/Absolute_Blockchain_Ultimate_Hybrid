"""Wave 42 — WASM VM SQLite persistence + bridge relayer status API."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


def test_wasm_deploy_persists_and_charges_fee():
    from features.wasm_vm import WASMVirtualMachine
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "w.db"))
    db.initialize()
    owner = "0x" + "a" * 40
    db.set_balance(owner, 1.0)

    vm1 = WASMVirtualMachine(db=db)
    addr = vm1.deploy("fn hello() {}", owner, "TestContract")
    assert addr
    assert addr.startswith("wasm_")
    assert db.get_balance(owner) == 1.0 - vm1.DEPLOY_FEE

    vm2 = WASMVirtualMachine(db=db)
    assert addr in vm2.contracts
    assert vm2.get_stats()["persisted"] is True


def test_wasm_call_persists_storage():
    from features.wasm_vm import WASMVirtualMachine
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "c.db"))
    db.initialize()
    owner = "0x" + "b" * 40
    db.set_balance(owner, 10.0)

    vm = WASMVirtualMachine(db=db)
    addr = vm.deploy("token", owner, "Tok", {"initialSupply": 1000})
    out = vm.call(addr, "transfer", {"to": "0x" + "c" * 40, "amount": 100}, owner)
    assert out["success"] is True

    vm2 = WASMVirtualMachine(db=db)
    bal = vm2.call(addr, "balanceOf", {"account": owner}, owner)
    assert bal["result"] == 900


def test_wasm_deploy_rejects_low_balance():
    from features.wasm_vm import WASMVirtualMachine
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "r.db"))
    db.initialize()
    owner = "0x" + "d" * 40
    db.set_balance(owner, 0.001)

    vm = WASMVirtualMachine(db=db)
    assert vm.deploy("code", owner) is None


def test_bridge_relayer_status_helper():
    from api.http import _build_bridge_relayer_status
    from runtime.config import Config
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db = Database(os.path.join(tmp, "br.db"))
    db.initialize()
    cfg = Config(db_path=db.db_path)
    st = _build_bridge_relayer_status(cfg, db)
    assert "pending_locks" in st
    assert "relayer_script" in st
    assert "l1_outbound" in st
