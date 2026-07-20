# codex-helper

`codex-helper` is a self-contained, Git-versioned harness for portable Codex guidance, host-selected configuration, agents, rules, skills, utilities, and health checks.

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

Create the ignored host secret file from `.env-<host>.example` when that host config needs credentials. Review the printed plan before answering `y`. The installer creates individual links, including `~/.codex/config.toml` → the selected Git-tracked `sources/config/config-<host>.toml`. This global config target is independent of a runtime-specific `CODEX_HOME`.

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
| `codex-harness host init NAME` | Atomically create `config-NAME.toml` from the safe default. |
| `codex-harness snapshot --json` | Back up only declared targets, live config, and harness state. |
| `codex-harness apply --yes` | Transactionally apply the reviewed plan. |
| `codex-harness restore ID --yes` | Restore a snapshot receipt. |
| `codex-harness unlink --yes` | Remove matching links and materialize the recorded config as a `0600` file. |
| `codex-harness doctor --json` | Validate sources, links, config ownership, secrets, and versions. |
| `codex-external-review --repo PATH` | Run one bounded, ephemeral, read-only review cycle. |

Global options such as `--host rock` precede the command. Add `--json` where supported for automation.

## Ownership boundary

This repository does not own Codex authentication, sessions, logs, caches, databases, plugin payloads, desktop/UI state, `rules/default.rules`, or undeclared skills. Host config files may track the corresponding Codex configuration choices, while secret values stay in ignored `.env-<host>` files.

## Feature delivery workflow

`$feature-delivery` runs only when the user explicitly invokes it; merely mentioning or editing the skill is not an invocation. An active invocation authorizes planner/scanner/developer/reviewer/verifier subagents without another request. When the root delegates a bounded task, that subagent performs the scope and the root does not duplicate it.

A single or sequential developer may use the active checkout unless the root requests isolation. Before a second concurrent developer starts, the root verifies or creates a separate worktree so writable developers never share a checkout. The developer profile defaults to `workspace-write`, but actual edits remain bounded by the parent, user, and system permission boundary.

## Documentation

- [Architecture](docs/architecture.md)
- [Operations](docs/operations.md)
- [Cross-machine bootstrap](docs/cross-machine-bootstrap.md)
- [Sources and adaptations](docs/sources.md)
- [User guide](docs/user-guide.md)
- [Codex external review agent research](docs/research/codex-external-review-agents-2026-07.md)
- [SDD/TDD skill recommendations](docs/research/sdd-tdd-skills-2026-07.md)
