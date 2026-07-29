# Architecture

## Ownership model

`manifest.toml` is the authoritative inventory. Each static asset declares an ID, source, target, category, scope, and version. Static targets are individual symbolic links, so installing one profile or skill never replaces an entire runtime-owned directory.

The manifest `[config]` table declares a host source pattern, safe default, live target, asset ID, and version. The harness resolves one Git-tracked canonical file such as `sources/config/config-gems.toml` and exposes it as the synthetic `global-config` asset (`category = "config"`, `kind = "symlink"`). `$HOME/.codex/config.toml` is an individual symbolic link to that selected source even when an embedded runtime supplies another `CODEX_HOME`. Machine-specific non-secret settings travel through Git; secrets are read from the ignored project-root `.env-<host>` file by the tracked MCP loader.

Host selection precedence is `--host`, then `CODEX_HELPER_HOST`, then the normalized short hostname (`GEMS.local` becomes `gems`). An unknown explicit or environment-selected host fails closed. Only an unknown implicit hostname falls back to `config-default.toml`, and plan/inventory output marks that fallback.

## State and recovery

The harness writes `~/.codex/.codex-helper/state.json` after a successful apply. It records the harness version, selected host, and declared asset endpoints including the exact `global-config` source. It contains no credentials. Runtime assets may still use a runtime-specific `CODEX_HOME`, but global config state and receipts remain under `$HOME/.codex`.

Before replacing or removing a declared target, the harness creates a timestamped backup receipt below `~/.codex/backups/codex-helper/`. The receipt records the prior type, bytes, and file metadata of each exact target. Writes and links use temporary siblings followed by atomic replacement. A failed apply restores receipt entries in reverse order, including a pre-existing real config and its mode.

## Runtime exclusions

Authentication, sessions, logs, caches, databases, plugins, marketplaces, projects, desktop/UI state, the runtime default rule file, and undeclared skills are outside manifest ownership. Snapshot, apply, restore, and unlink do not enumerate or copy those areas.

## Agent workflows

`parallel-review` coordinates bounded native scanner, reviewer, and verifier roles for independent read-heavy concerns. The root agent retains final judgment and all write authority.

`dual-loop-review` first requires fresh local evidence, then invokes a separate ephemeral Codex process in a read-only sandbox with a structured verdict. It permits at most five cycles.

`feature-delivery` is explicit-only and root-inline by default. Mentioning or editing the skill is not activation. An active invocation authorizes subagents without a second request. A delegated scope has one active performer: the subagent owns and executes it while the root limits itself to coordination, integration, or non-overlapping work. Planner, scanner, reviewer, and verifier are read-only; the developer profile defaults to `workspace-write`; and the root retains integration authority.

A single or sequential developer may use the active checkout. Worktree isolation is not otherwise mandatory. Before launching a second concurrent developer, the root verifies or creates a separate worktree; concurrent writable developers never share one checkout.

## Independence boundary

This repository is the sole operational source for the Codex harness. Managed links must resolve inside this checkout, and operational scripts never inspect a sibling assistant harness. `doctor` enforces both conditions from local source and link metadata.
