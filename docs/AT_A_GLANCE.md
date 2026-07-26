# At a glance

One-screen card for people who do not read long READMEs. Full detail: [README](../README.md) · proof ledger: [EVIDENCE_MATRIX](EVIDENCE_MATRIX.md).

## What this is

Hybrid **Python + Rust** L1 node with prod-profile Docker mesh, RocksDB, REST/JSON-RPC, `abs_native`, EVM path.

## What it is not

Public audited mainnet · listed ABS token · investment product · bridge ON on live mesh.

## Status

| | |
|---|---|
| Tag | **[v1.3.205](../RELEASE_NOTES_v1.3.205.md)** |
| CI | Ubuntu `test.yml` + docker + security + fuzz |
| 48h soak | **PASS** |
| Self-check | `.\scripts\operator_verify.ps1 -SkipNativeBuild` · `make test-quick` |
| Run | `python main.py` → `:8080` |
| Prod mesh | `778888` profile → `:18180–18182` |

## Proven vs not (honest)

| Proven | Not claimed |
|--------|-------------|
| 3-node prod-profile mesh | Public mainnet |
| 48h soak PASS | External L1 / contract audit |
| Failover + signed tx + EVM on mesh | Tip proof / Long-Range / libp2p |
| Bridge **OFF** on live mesh | Listed ABS / investment product |

## Where code lives

| Path | Role |
|------|------|
| `native/abs_native/` | Rust (look for `Cargo.toml`) |
| `network/` | P2P control plane |
| `scripts/` | Ops gates |
| `Makefile` | Linux/macOS shortcuts |

## Next click

- Gaps to mainnet: [MAINNET_GAP_ANALYSIS](MAINNET_GAP_ANALYSIS.md)
- Commands: [COMMANDS_REFERENCE](COMMANDS_REFERENCE.md)
- Contribute: [CONTRIBUTING](../CONTRIBUTING.md)
- GitHub About paste: [REPO_PROFILE](../.github/REPO_PROFILE.md)
