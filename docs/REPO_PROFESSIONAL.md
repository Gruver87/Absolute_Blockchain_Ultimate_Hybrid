# Professional repository posture

Comparison against common **professional open-source / blockchain** repo hygiene
(OpenZeppelin Contracts, Ethereum clients, audited protocol monorepos) — focused
on what Absolute already has vs what was added, **without** claiming mainnet or
audit completion.

## Industry baseline (what serious repos ship)

| Practice | Typical peers | Absolute |
|----------|---------------|----------|
| Clear README + honesty | Required | Yes — evidence-first, not-mainnet |
| LICENSE | MIT/Apache | [LICENSE](../LICENSE) MIT |
| SECURITY.md + private disclosure | Required | [SECURITY.md](../SECURITY.md) |
| CONTRIBUTING + CoC | Common | Yes |
| ISSUE / PR templates | Common | Yes |
| CODEOWNERS | Common | Yes |
| CI badges (test / security / fuzz) | Common | Yes |
| Dependabot / Renovate | Common | **Yes** (`.github/dependabot.yml`) |
| EditorConfig | Common | **Yes** (`.editorconfig`) |
| SUPPORT.md | Common | **Yes** |
| Release process doc | Common | [docs/RELEASING.md](RELEASING.md) |
| Audit status page (honest) | Best practice | [docs/AUDITS.md](AUDITS.md) |
| SBOM on release | Growing best practice | Workflow `sbom-on-release.yml` |
| External audit PDF + bounty | Mainnet-grade | **Pending** (org) |
| Formal verification / BFT paper | Research / L1 leaders | Not claimed |

## What Absolute already leads on (in-repo)

- Industrial wave verify (`verify_industrial_waves`) + fail-closed prod gates
- Native Rust crypto/P2P gates with honesty limits in every release note
- Evidence matrix + mainnet gap analysis (anti-marketing)
- 3-node Docker prod-profile mesh + soak evidence path
- Incident / observability / TLS / ceremony docs

## What still requires humans / org (cannot be “coded away”)

1. Pin `GENESIS_CEREMONY_HASH` for live ceremony
2. Commission and publish external security audit
3. Legal / listing / public validator ops (if ever)

Until those land, README and gates must keep saying **not** public mainnet.
