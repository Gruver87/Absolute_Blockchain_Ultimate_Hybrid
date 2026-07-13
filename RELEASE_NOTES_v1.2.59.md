# Release Notes — v1.2.59

## P2P maintenance + monolith status

- **`_maintenance_loop`** runs on the P2P event loop and periodically calls `_prune_stale_peers()` — evicts stale peers, low-score peers (when configured), and expires bans without waiting for reconnect.
- **`GET /status.monolith_summary`** — one-glance readiness: deployment mode, P2P hardened/sync status, consensus unified path, native crypto, bridge.

## Verify

```powershell
pytest tests/unit/test_p2p_industrial.py -q
curl http://127.0.0.1:8080/status | jq '{p2p_summary, monolith_summary}'
```
