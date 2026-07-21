# Release notes — v1.3.10

**Date:** 2026-07-21  
**Theme:** Semantic peer-tx honesty + mesh Redis JSON + compose freeze + k8s in post_soak

## P2P honesty

- Semantic / mempool peer tx rejects → warning + `ops_errors.peer_tx_reject` (not silent `debug`)
- Gossip `_handle_new_tx` strikes `bad_peer_tx` on reject
- Mempool batch wire/mempool drops also increment the counter
- Prometheus `abs_p2p_peer_tx_reject_total` + alert/panel

## Deploy / gates

- Mesh prod JSON (`mesh1/2/3`) declares `redis_rate_limit_enabled` + `redis_url` (compose already injected env)
- industrial_gate: mesh/k8s redis keys; `p2p_evict_min_score` shared; compose↔mesh JSON numeric freeze for Rocks/P2P knobs
- `post_soak_verify` runs `k8s_prod_gate.py` after industrial_gate

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
