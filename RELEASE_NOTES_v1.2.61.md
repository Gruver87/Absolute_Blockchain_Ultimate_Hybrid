# Release Notes — v1.2.61

## P2P handshake hardening + recovery drill

- **chain_id mismatch** during handshake now records a strike (same ban policy as wire abuse).
- **`handshake_rejects`** counter exposed in `/p2p/security`, topology, and `/status.p2p_summary`.
- **`prod-mesh3-recovery`** runs P2P security checks after successful node2 rejoin.
- **`docker_prod_3node.ps1 -RecoveryDrill`** — one-shot rebuild + failover drill.
- **Hotfix:** rate limit drops excess wire traffic without ban strikes (prod hub was banned during block sync).

## Verify

```powershell
pytest tests/unit/test_p2p_industrial.py -q
.\scripts\prod_mesh_failover.ps1
# or full rebuild + drill:
.\scripts\docker_prod_3node.ps1 -KeepVolumes -NoCloneDb -RecoveryDrill
```
