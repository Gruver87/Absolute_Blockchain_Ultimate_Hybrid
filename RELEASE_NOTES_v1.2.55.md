# Release Notes — v1.2.55

Date: 2026-07-13

## P2P auto mode fix

When Docker prod mesh is running on `:18180–:18182`, plain `-P2P` no longer runs heavy `prod-mesh3-live` checks by accident.

| Flag | Behavior |
|------|----------|
| `--mode auto --prefer-devnet` | devnet `:8080+` or isolated CI (default for `test_blockchain_full -P2P`) |
| `--mode auto --prefer-prod-mesh` | prod mesh when all three prod nodes are up |
| `-ProdMesh` / `--mode prod-mesh3-live` | explicit prod mesh gate |

## Harness timeout fix

Prod mesh consistency harness could fail with `node1 harness: timed out` because the client used a 10s urllib timeout while the server waits up to ~12s for peer state roots.

Now `verify_p2p_ci` calls `/chain/consistency/harness?quick=1&peer_timeout=3` with **≥45s** client timeout on prod ports.
