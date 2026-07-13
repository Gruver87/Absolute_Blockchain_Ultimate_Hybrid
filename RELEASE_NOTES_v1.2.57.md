# Release Notes — v1.2.57

## P2P security hardening

Industrial mesh protection beyond wire size and rate limits:

- **Strike → ban:** peers exceeding rate limits or sending invalid wire payloads accumulate strikes; after `p2p_rate_limit_strikes` (default 5) they are banned for `p2p_ban_seconds` (default 300).
- **Message allowlist:** only known protocol types are accepted; unknown types trigger strikes and disconnect.
- **Eviction:** when `p2p_evict_min_score` > 0 and multiple peers are connected, peers below the health score threshold are dropped during prune/reconnect.

## Observability

- `GET /p2p/security` — bans, limits, eviction policy
- `/p2p/topology` now includes `security` block and per-peer `strikes` / `banned`
- `probe_mesh_nodes.ps1 -Deep` shows active ban count and rate limit config

## Config (env)

| Variable | Default |
|----------|---------|
| `P2P_MAX_MESSAGES_PER_SEC` | 500 |
| `P2P_BAN_SECONDS` | 300 |
| `P2P_RATE_LIMIT_STRIKES` | 5 |
| `P2P_EVICT_MIN_SCORE` | 0 (off) |

## Verify

```powershell
pytest tests/unit/test_p2p_industrial.py -q
python scripts/verify_p2p_ci.py --mode auto --prefer-devnet
.\scripts\probe_mesh_nodes.ps1 -Deep
```
