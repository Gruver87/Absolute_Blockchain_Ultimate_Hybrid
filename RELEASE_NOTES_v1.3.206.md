# Release notes — v1.3.206

## Summary

**Architecture ship: tip-safety + P2P transport/dispatch boundaries (production-ready layers):**

1. **Tip-safety** (`consensus/tip_safety`) — domain + shadow + enforce on import; **required in prod** via `prod_gate` / `Config.validate()`.
2. **P2P transport** (`network/transport`) — `NativeTransportAdapter`, reject taxonomy, live ingress/egress wiring, metrics `abs_p2p_transport_*`.
3. **P2P dispatcher** (`network/p2p_dispatch`) — Handler Registry; `_handle_message` application switch extracted; tip-evidence DI without import cycles.

## Changes

- `consensus/tip_safety/` — TipState, ReorgPolicy, ForkChoice, TipSafetyService, TipSafetyShadowObserver
- `network/transport/` — ports, reject counters, NativeTransportAdapter (Step A–C)
- `network/p2p_dispatch/` — P2PDispatcher, HandlerRegistry, TipSafetyEvidenceBridge (Step D)
- `network/p2p_node.py` — transport adapter + dispatcher host surface; type-switch → `dispatcher.dispatch`
- Config: `tip_safety_shadow` / `tip_safety_enforce` (prod requires enforce)
- ADR: `docs/adr/0001-tip-safety.md`, `docs/adr/0002-p2p-transport-boundary.md`
- Evidence matrix + README footer refreshed
- `.gitignore`: `dist/`, wheels, local pytest dumps
- `node_version`: `1.3.206-industrial`

## Honesty

- Tip-safety import gate ≠ tip proof / Long-Range / BFT quorum
- Transport boundary ≠ libp2p; dispatcher ≠ native shell ownership
- Not a launched public mainnet

## Verify

```text
python -m pytest tests/unit -k "tip_safety or p2p_transport or transport_wiring or p2p_dispatch" -q
python scripts/prod_gate.py
python scripts/k8s_prod_gate.py
```
