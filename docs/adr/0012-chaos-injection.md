# ADR 0012 — Chaos Injection Framework

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Absolute Blockchain maintainers

## Context

Fault vocabulary lived fragmented across FakeStorage, FakeConsensus, FakeEvmBridge,
and FakeRpcClient. There was no unified TotalChaosEngine to bombard all ports in
parallel under fail-closed DoD. Live Rust `P2PNativeConn` has no tear hooks —
chaos must wrap Transport/codec seams, not `allow_threads` kernels.

## Decision

1. **`TotalChaosEngine`** — async scheduler firing weighted `FaultKind` injections
   across network / storage / consensus / bridge / RPC ChaosPort injectors.
2. **Port-wrapper injection only** — harness DI; production `main.py` never arms chaos.
3. **Outcomes:** `FAIL_CLOSED` | `RECOVERED` | `PANIC` | `LEAK_SIGNAL` (last two fail tests).
4. **Bombardment:** `tests/chaos/test_total_chaos_bombardment.py` (≥500 injections /
   ≤120s locally; smoke via env for CI).
5. **Memory honesty:** bounded gauges (`active_tasks`, `armed_faults`); not ASan/Valgrind.

## Definition of Done

- This ADR present; industrial_gate needles for ADR + `TotalChaosEngine`
- Injectors + observer + bombardment test green
- No chaos arming on NodeOrchestrator happy path
