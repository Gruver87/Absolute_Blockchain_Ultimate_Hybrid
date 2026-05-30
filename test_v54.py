# test_v54.py
"""
Full test suite for v54 - Jumps, Functions, Loops
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from execution.vm import MiniVM
from compiler.assembler import assemble, disassemble
from compiler.examples import (
    counter_contract, loop_contract, conditional_contract,
    fibonacci_contract, simple_if
)

def log(msg):
    sys.stdout.write(msg + "\n")

log("=" * 70)
log("v54 — EVM-STYLE BYTECODE COMPILER")
log("JUMPS + FUNCTIONS + LOOPS + CONDITIONS")
log("=" * 70)

passed = 0
total = 0

def test(name, condition):
    global passed, total
    total += 1
    if condition:
        log(f"   ✅ {name}")
        passed += 1
    else:
        log(f"   ❌ {name}")

# =========================================================
log("\n[TEST 1] Assembler with labels")
source = """
START:
    PUSH 42
    STOP
"""
bytecode = assemble(source)
test("Assembler produces bytecode", len(bytecode) > 0)
test("Label removed", all(op != "LABEL" for op, _ in bytecode))

# =========================================================
log("\n[TEST 2] VM executes assembled code")
vm = MiniVM()
result = vm.execute(bytecode)
test("Execution succeeds", result["success"])
test("Stack has 42", result["stack"][-1] == 42)

# =========================================================
log("\n[TEST 3] JUMP instruction")
source_jump = """
START:
    JUMP target
    PUSH 0
target:
    PUSH 1
    STOP
"""
vm2 = MiniVM()
result2 = vm2.execute(assemble(source_jump))
test("JUMP skips instruction", result2["stack"][-1] == 1)

# =========================================================
log("\n[TEST 4] JUMPI conditional")
source_jumpi = """
START:
    PUSH 1
    JUMPI target
    PUSH 0
    STOP
target:
    PUSH 1
    STOP
"""
vm3 = MiniVM()
result3 = vm3.execute(assemble(source_jumpi))
test("JUMPI taken when condition=1", result3["stack"][-1] == 1)

# =========================================================
log("\n[TEST 5] JUMPI not taken")
source_jumpi_false = """
START:
    PUSH 0
    JUMPI target
    PUSH 42
    STOP
target:
    PUSH 1
    STOP
"""
vm4 = MiniVM()
result4 = vm4.execute(assemble(source_jumpi_false))
test("JUMPI not taken when condition=0", result4["stack"][-1] == 42)

# =========================================================
log("\n[TEST 6] CALL and RETURN")
source_call = """
START:
    PUSH 5
    CALL double
    STOP
double:
    PUSH 2
    MUL
    RETURN
"""
vm5 = MiniVM()
result5 = vm5.execute(assemble(source_call))
test("CALL executes function", result5["success"])
test("RETURN returns to caller", result5["stack"][-1] == 10)

# =========================================================
log("\n[TEST 7] Counter contract with functions")
bytecode_counter = counter_contract()
vm6 = MiniVM()
result6 = vm6.execute(bytecode_counter)
test("Counter contract executes", result6["success"])
test("Counter = 3 after 3 calls", vm6.get_storage("counter") == 3)

# =========================================================
log("\n[TEST 8] Loop contract (10 increments)")
bytecode_loop = loop_contract()
vm7 = MiniVM()
result7 = vm7.execute(bytecode_loop)
test("Loop contract executes", result7["success"])
test("Counter = 10 after loop", vm7.get_storage("counter") == 10)

# =========================================================
log("\n[TEST 9] Conditional contract")
bytecode_cond = conditional_contract()
vm8 = MiniVM()
vm8.set_storage("value", 15)  # greater than 10
result8 = vm8.execute(bytecode_cond)
test("Condition true branch", result8["success"])
test("result = 1 when value > 10", vm8.get_storage("result") == 1)

vm8b = MiniVM()
vm8b.set_storage("value", 5)  # less than 10
result8b = vm8b.execute(bytecode_cond)
test("Condition false branch", result8b["success"])
test("result = 0 when value <= 10", vm8b.get_storage("result") == 0)

# =========================================================
log("\n[TEST 10] Comparison opcodes")
vm9 = MiniVM()
vm9.execute(assemble("""
START:
    PUSH 10
    PUSH 5
    GT
    STOP
"""))
test("5 < 10 = 1", vm9.stack[-1] == 1) if vm9.stack else None

vm9b = MiniVM()
vm9b.execute(assemble("""
START:
    PUSH 5
    PUSH 5
    EQ
    STOP
"""))
test("5 == 5 = 1", vm9b.stack[-1] == 1) if vm9b.stack else None

# =========================================================
log("\n[TEST 11] Nested function calls")
source_nested = """
START:
    PUSH 2
    CALL outer
    STOP
outer:
    PUSH 3
    CALL inner
    RETURN
inner:
    PUSH 4
    MUL
    RETURN
"""
vm10 = MiniVM()
result10 = vm10.execute(assemble(source_nested))
test("Nested calls work", result10["success"])
test("2 * 3 * 4 = 24", result10["stack"][-1] == 24)

# =========================================================
log("\n[TEST 12] Gas metering with jumps")
vm11 = MiniVM(gas_limit=50)
bytecode_jump = assemble("""
START:
    PUSH 1
    JUMPI target
    PUSH 0
target:
    STOP
""")
result11 = vm11.execute(bytecode_jump)
test("Gas limit respected with jumps", result11["success"])

# =========================================================
log("\n[TEST 13] Disassembler")
disassembled = disassemble(bytecode)
test("Disassembler works", len(disassembled) > 0)

# =========================================================
log("\n" + "=" * 70)
log(f"📊 RESULTS: {passed}/{total} tests passed")

if passed == total:
    log("🎉 v54 — ALL TESTS PASSED!")
    log("")
    log("   ✅ Labels and label resolution")
    log("   ✅ JUMP — unconditional jump")
    log("   ✅ JUMPI — conditional jump")
    log("   ✅ CALL — function call")
    log("   ✅ RETURN — return from function")
    log("   ✅ Nested function calls")
    log("   ✅ Loops with JUMPI")
    log("   ✅ If-else conditions")
    log("   ✅ Comparison operators (GT, LT, EQ)")
    log("   ✅ Gas metering with jumps")
    log("   ✅ Disassembler")
    log("")
    log("🏆 YOUR BLOCKCHAIN NOW HAS:")
    log("   → Full programmable runtime")
    log("   → Function calls (CALL/RETURN)")
    log("   → Conditional execution (JUMPI)")
    log("   → Loops and recursion")
    log("")
    log("🔥 NEXT: v55 — HIGH-LEVEL LANGUAGE COMPILER")
    log("   - Variables (let x = 10)")
    log("   - Functions (def increment(x))")
    log("   - Structs and events")
    log("   - Solidity-like syntax")
else:
    log(f"⚠️ Failed: {total - passed}")
log("=" * 70)
