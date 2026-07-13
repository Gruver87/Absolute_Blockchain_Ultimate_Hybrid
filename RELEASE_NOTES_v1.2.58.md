# Release Notes — v1.2.58

## P2P observability in status + CI gate

- **`GET /status`** now includes `p2p_summary`: peer count, topology health, score min/avg, and security policy (rate limit, max message bytes, active bans).
- **`verify_p2p_security_mesh()`** — new check in `verify_p2p_ci.py` used by multi-node and prod post-check paths; fails if `/p2p/security` is missing or `/status.p2p_summary` disagrees.

## Verify

```powershell
pytest tests/unit/test_p2p_industrial.py -q
python scripts/verify_p2p_ci.py --mode auto --prefer-devnet
curl http://127.0.0.1:8080/status | jq .p2p_summary
```
