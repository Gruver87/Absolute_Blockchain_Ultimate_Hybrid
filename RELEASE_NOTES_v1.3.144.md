# Release notes — v1.3.144

## Summary

**Industrial mempool DoS honesty (no simplifications):**

1. **Native shell solicit-armed gate** — `read_message_loop_events(..., mempool_solicit_armed=false)` refuses `MSG_MEMPOOL` as `unsolicited_mempool` **before** batch ECDSA (up to 500 sigs).
2. **Python arms only during pull** — `_mempool_solicit_armed_for` is true only while a waiter has `kind=mempool`.
3. Sequel to v1.3.131 (ingest solicit-only) + v1.3.143 (cheap refuse / primary rate).

## Changes

- `native/abs_native/src/p2p_transport.rs` — `mempool_solicit_armed` on loop shell
- `network/p2p_node.py` — arm flag + shell strike counter
- Metrics: `native_mempool_solicit_armed_shell`
- `node_version`: `1.3.144-industrial`

## Honesty

- Soft CPU refuse for unsolicited batch — **not** anti-Sybil, not tip proof, not libp2p, not fee-market, not public mainnet

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13144_mempool_solicit_armed_shell.py tests/unit/test_v13119_p2p_native_mempool_semantic_gate.py -q
```
