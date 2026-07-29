# Operations

## Safe update sequence

Run these commands in order from a clean checkout:

```bash
git pull --ff-only
codex-harness plan
codex-harness apply --yes
codex-harness doctor
```

Read the plan before applying. If the plan contains an unexpected target, stop and inspect `manifest.toml`; do not approve it speculatively.

## Daily inspection

```bash
codex-harness status --json
codex-harness inventory --json
codex-harness list --kind skills --json
codex-harness version --json
```

Read-only commands return 0 for a healthy/current result. `status` and `doctor` return 1 for drift or an unhealthy check. Manifest/argument errors return 2, preserved conflicts return 3, and an apply that restored its pre-operation snapshot returns 4.

## Skill activation

Inspect the two-level state before changing it:

```bash
codex-harness skill list --json
codex-harness skill status parallel-review --json
```

For a Git-shared default, change only that skill asset's `enabled` boolean in `manifest.toml`, then use the safe update sequence. For this machine only, use:

```bash
codex-harness skill disable parallel-review
codex-harness skill enable parallel-review
codex-harness skill reset parallel-review
```

`skill reset` removes the local override and reconciles the link to the manifest default. Toggle commands never replace a foreign file, directory, or link. Start a new Codex task after a state change so skill discovery uses the new link set.

## Feature-delivery operation

The managed `feature-delivery` skill is explicit-only. Mentioning its name or changing its contract is not invocation. An active `$feature-delivery` invocation authorizes subagents without a separate delegation request, although root-inline execution remains valid. After the root delegates a bounded scope, the subagent performs it exclusively; the root does not duplicate that work and keeps the parent active for coordination and integration.

If the skill is unavailable or machine-locally disabled, global guidance does not require the missing skill. The root can continue inline or use another chosen workflow without attempting to invoke it.

The root assigns and reports each `role instance - task name` label, allocates repeatable-role numbers monotonically, and reuses a number only for a same-thread follow-up. Planner, scanner, reviewer, and verifier remain read-only; the developer profile defaults to `workspace-write`, but actual edits remain bounded by the parent/user/system permission boundary. The root owns scope and integration; commits and pushes remain root responsibilities subject to user/system authorization.

Native badge width and ellipsis are client-owned, with no harness configuration. A nickname or native badge may truncate, so the root keeps the full label in dispatch, progress, and completion body text.

For a machine-local change, use the normal safe toggle commands:

```bash
codex-harness skill disable feature-delivery
codex-harness skill enable feature-delivery
codex-harness skill reset feature-delivery
```

Each toggle changes the local preference and managed link only when safe. Start a new Codex task after toggling because an already-open task can retain loaded skill instructions.

## Snapshots and recovery

Create a receipt before manual maintenance:

```bash
codex-harness snapshot --json
```

Restore a reviewed receipt or remove the harness wiring only with explicit confirmation:

```bash
codex-harness restore SNAPSHOT_ID --yes
codex-harness unlink --yes
```

Restore may replace the exact targets listed by the receipt. Unlink removes only links that still point at recorded sources. When the live config link still matches the config source recorded in state, unlink materializes those canonical bytes as a `0600` real `config.toml`; a foreign file or link is preserved and reported as a conflict.

## Host configs

Pass the host before the subcommand:

```bash
codex-harness --host rock plan --json
codex-harness --host rock apply --yes
```

The selected source is `sources/config/config-<host>.toml`; it is the canonical tracked machine config. Selection precedence is `--host` > `CODEX_HELPER_HOST` > normalized short hostname. Its live target is always `$HOME/.codex/config.toml`, independent of runtime `CODEX_HOME`.

Create a new host source atomically from the safe baseline with `codex-harness host init NAME`, review it, and commit it before applying. Machine-specific paths and choices may remain in that host file. Move credentials to the ignored `.env-NAME`, commit a redacted `.env-NAME.example`, and use `bin/codex-mcp-env` for commands that need those values. `doctor` parses every `config-*.toml` and rejects literal bearer secrets without printing values.

Every v0.4.1 host config must set `features.multi_agent = true`, `agents.max_threads = 4`, and `agents.max_depth = 1`.

## External review

Native `$parallel-review` uses Codex subagents and therefore needs a persistent parent task. Run it from the app, an interactive CLI task, or a non-ephemeral `codex exec` invocation. Do not combine it with `codex exec --ephemeral`; ephemeral mode is reserved here for the single-process external reviewer below.

After local tests have fresh evidence:

```bash
codex-external-review --repo "$PWD" --cycle 1 --evidence .codex-loop/evidence.md
```

Validate every finding locally. A `changes_requested` verdict can lead to cycle 2; cycles 3 through 5 are reserved for distinct remaining issues. Never exceed five cycles.
