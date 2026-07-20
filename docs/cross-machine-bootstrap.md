# Cross-machine bootstrap

## New machine

1. Install Git, `uv`, and Codex CLI 0.144.5 or newer.
2. Clone this repository to a stable path.
3. Choose an existing tracked host config (`config-gems.toml`, `config-rock.toml`) or create one from the safe default:

   ```bash
   ./bin/codex-harness host init laptop
   git add sources/config/config-laptop.toml
   git commit -m "config: add laptop Codex config"
   ```

4. If that config references local credentials, copy `.env-laptop.example` to the ignored `.env-laptop`, fill it locally, and set mode `0600`. Never commit the real `.env-laptop`.

5. Preview and install:

   ```bash
   ./install.sh --host laptop
   ```

6. Ensure `$HOME/.local/bin` is on `PATH`, then restart Codex so global guidance, profiles, agents, rules, and skills are rediscovered.

## Host selection and tracked settings

`manifest.toml` is authoritative: `[config]` declares `sources/config/config-{host}.toml`, `config-default.toml`, the live target, and the synthetic `global-config` identity. Selection precedence is explicit `--host`, then `CODEX_HELPER_HOST`, then the lowercase short hostname. Thus `GEMS.local` selects `config-gems.toml`. A typo in an explicit option or environment variable fails closed. An unregistered implicit hostname falls back to `config-default.toml` and reports `fallback: true` in JSON plan/inventory output.

Commit `sources/config/config-NAME.toml` when that machine's non-secret Codex settings should follow it across rebuilds. Host files may contain machine paths, MCP definitions, plugin choices, project trust settings, and UI preferences. v0.4.1 still requires `features.multi_agent = true`, `agents.max_threads = 4`, and `agents.max_depth = 1` on every host.

The tracked GEMS config sets `model_context_window = 1000000` and `model_auto_compact_token_limit = 850000` with `scope = "total"`, so automatic compaction begins at 85% of the configured context window. The manifest records this global-config contract as asset version 1.2.0.

Keep credentials outside host configs. Put each host's values in the ignored project-root `.env-NAME`; commit only `.env-NAME.example`. The tracked `bin/codex-mcp-env` loader selects the matching file and appends the requested secret to the MCP command. `codex-harness doctor` rejects literal bearer credentials in tracked TOML and checks the required multi-agent settings without exposing values.

The repository path is not embedded in the manifest. Every source is resolved relative to the current clone, so another machine can use a different clone location.

Skill `enabled` defaults in `manifest.toml` travel with Git. Machine-local choices made by `codex-harness skill enable|disable` stay in `$HOME/.codex/.codex-helper/preferences.toml` and do not travel to another machine; use `codex-harness skill reset NAME` to return that machine to the shared default.

## Skill behavior rollout

`manifest.toml` records feature-delivery 1.2.0. It remains implicit-invocation disabled: mentioning or editing the skill is not a workflow call. An active explicit invocation authorizes subagents, and each delegated scope is performed by its assigned subagent without overlapping root execution. A single developer does not require a separate worktree; before a second concurrent developer starts, verify or create an isolated worktree.

Apply this contract on another machine with:

```bash
git pull --ff-only
codex-harness plan
codex-harness apply --yes
codex-harness doctor
```

Start a new Codex task after updating so the client reloads the skill metadata and global `AGENTS.md`.

## Migration from a real config

On the first 0.4.1 apply, an existing real `$HOME/.codex/config.toml` is a reviewed conflict. The global config location deliberately ignores an embedded runtime's alternate `CODEX_HOME`. Run `plan`, inspect the selected `global-config` source, then use `apply --yes`. A second apply is a no-op.

Before upgrading a v0.3 machine, inspect its ignored `sources/config/hosts/<name>.local.toml`. Move non-secret settings into `sources/config/config-<name>.toml` and secrets into `.env-<name>`, then remove the obsolete local overlay. Do not use `git add -f`.

Changing hosts is visible drift: run `codex-harness --host NEW plan --json`, review the new source, then run `codex-harness --host NEW apply --yes`. Applying a drifted, broken, or conflicting config link without `--yes` preserves the existing link and state. Do not manually repoint the link because state must record the same source for safe unlink and doctor checks.

## Updates and rollback

Use the safe update sequence in `docs/operations.md`. Each apply creates a receipt automatically. If a new revision behaves incorrectly, restore the reported snapshot ID:

```bash
codex-harness restore SNAPSHOT_ID --yes
```

If the repository is being removed from the machine, run `codex-harness unlink --yes` first. It converts the state-recorded config link to a standalone `0600` real file before the checkout disappears, while keeping runtime-owned Codex state and unmanaged skills intact. A foreign config is never overwritten and produces a conflict.
