# Release notes — v1.3.17

**Date:** 2026-07-21  
**Theme:** Never-probed wire honesty (solo ≠ probed-ok)

## Sync / Prometheus

- Solo / no-peer `sync_state` leaves `_last_wire_probe_ok=None` (never probed)
- Prometheus `abs_sync_wire_probe_ok`: **-1** never probed, **0** failed, **1** ok
- `get_status()` exposes `wire_probe_probed`

## eth_syncing

- Peers present + never wire-probed → stay syncing (do not return `false`)

## P2P

- `ops_errors.peer_sync_fail` always present in security status

## Explicit non-goals

- Public mainnet / external audit complete
- Bridge L1 enablement
