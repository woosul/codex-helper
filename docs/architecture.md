# Architecture

## Ownership model

`manifest.toml` is the authoritative inventory. Each static asset declares an ID, source, target, category, scope, and version. Static targets are individual symbolic links, so installing one profile or skill never replaces an entire runtime-owned directory.

`~/.codex/config.toml` is deliberately different: it remains a real file. `sources/config/base.toml`, a tracked host overlay, and an optional ignored `.local.toml` overlay are combined. The merge engine removes only key paths recorded as previously owned, applies the new overlay, and preserves every unmanaged key and array-of-tables value.

## State and recovery

The harness writes `~/.codex/.codex-helper/state.json` after a successful apply. It records the harness version, selected host overlay, owned config leaf paths, and declared asset endpoints. It contains no credentials.

Before replacing or removing a declared target, the harness creates a timestamped backup receipt below `~/.codex/backups/codex-helper/`. The receipt records the prior type of each exact target and stores file or directory content only when that declared target existed. Writes and links use temporary siblings followed by atomic replacement. A failed apply restores receipt entries in reverse order.

## Runtime exclusions

Authentication, sessions, logs, caches, databases, plugins, marketplaces, projects, desktop/UI state, the runtime default rule file, and undeclared skills are outside manifest ownership. Snapshot, apply, restore, and unlink do not enumerate or copy those areas.

## Review workflows

`parallel-review` coordinates bounded native scanner, reviewer, and verifier roles for independent read-heavy concerns. The root agent retains final judgment and all write authority.

`dual-loop-review` first requires fresh local evidence, then invokes a separate ephemeral Codex process in a read-only sandbox with a structured verdict. It permits at most three cycles.

## Independence boundary

This repository is the sole operational source for the Codex harness. Managed links must resolve inside this checkout, and operational scripts never inspect a sibling assistant harness. `doctor` enforces both conditions from local source and link metadata.
