# codex-helper

`codex-helper` is a self-contained, Git-versioned harness for portable Codex guidance, configuration overlays, agents, rules, skills, utilities, and health checks.

## Requirements

- Git
- [`uv`](https://docs.astral.sh/uv/)
- Codex CLI 0.144.5 or newer

## First installation

```bash
git clone <your-repository-url> codex-helper
cd codex-helper
./install.sh --host rock
```

Review the printed plan before answering `y`. The installer creates individual links and merges only manifest-owned configuration keys.

## Commands

| Command | Purpose |
|---|---|
| `codex-harness plan` | Preview links and config changes without writing. |
| `codex-harness status` | Report drift; exit 1 when managed state differs. |
| `codex-harness inventory` | List managed assets, versions, sources, and state. |
| `codex-harness list --kind KIND` | Filter skills, agents, profiles, rules, or utilities. |
| `codex-harness skill list` | Show skill defaults, local overrides, effective state, and link state. |
| `codex-harness skill status NAME` | Inspect one managed skill by short name or asset ID. |
| `codex-harness skill enable NAME` | Force one skill ON on this machine and create its link. |
| `codex-harness skill disable NAME` | Force one skill OFF on this machine and remove its matching link. |
| `codex-harness skill reset NAME` | Remove the local override and return to the manifest default. |
| `codex-harness version [ASSET]` | Show harness or asset version metadata. |
| `codex-harness bootstrap` | Create only required parent directories. |
| `codex-harness host init NAME` | Create a tracked, non-secret host overlay skeleton. |
| `codex-harness snapshot --json` | Back up only declared targets, live config, and harness state. |
| `codex-harness apply --yes` | Transactionally apply the reviewed plan. |
| `codex-harness restore ID --yes` | Restore a snapshot receipt. |
| `codex-harness unlink --yes` | Remove matching managed links and owned config keys. |
| `codex-harness doctor --json` | Validate sources, links, config ownership, secrets, and versions. |
| `codex-external-review --repo PATH` | Run one bounded, ephemeral, read-only review cycle. |

Global options such as `--host rock` precede the command. Add `--json` where supported for automation.

## Ownership boundary

This repository does not own Codex authentication, sessions, logs, caches, databases, plugins, marketplaces, projects, desktop/UI state, `rules/default.rules`, or undeclared skills. Those remain runtime- or user-owned and are preserved.

## Documentation

- [Architecture](docs/architecture.md)
- [Operations](docs/operations.md)
- [Cross-machine bootstrap](docs/cross-machine-bootstrap.md)
- [Sources and adaptations](docs/sources.md)
- [User guide](docs/user-guide.md)
- [Codex external review agent research](docs/research/codex-external-review-agents-2026-07.md)
- [SDD/TDD skill recommendations](docs/research/sdd-tdd-skills-2026-07.md)
