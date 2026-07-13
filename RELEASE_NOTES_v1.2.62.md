# Release Notes — v1.2.62

## P2P sync-safe rate limits + gate coverage

- **Exempt types:** handshake, ping/pong, status, state-root, block/blocks payloads skip per-peer rate-limit counting — prod hub can sync without dropped gossip.
- **Industrial gate:** static `_check_p2p_hardening()` validates allowlist, security API, maintenance loop.
- **2-node verify:** `verify_pair` (devnet + `--mode ci`) now runs P2P security mesh checks.
- **Maintenance:** strike counters cleared when peers disconnect.

## Verify

```powershell
pytest tests/unit/test_p2p_industrial.py -q
python scripts/industrial_gate.py
python scripts/verify_p2p_ci.py --mode auto --prefer-prod-mesh
```
