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

Restore may replace the exact targets listed by the receipt. Unlink removes only links that still point at recorded sources, removes only recorded config paths, preserves `config.toml` as a real file, and reports externally changed targets as conflicts.

## Host overlays

Pass the host before the subcommand:

```bash
codex-harness --host rock plan --json
codex-harness --host rock apply --yes
```

Tracked host files contain portable non-secret preferences. Ignored `NAME.local.toml` files are for machine-local, non-versioned preferences; credentials still belong in environment variables or Codex credential storage.

## External review

After local tests have fresh evidence:

```bash
codex-external-review --repo "$PWD" --cycle 1 --evidence .codex-loop/evidence.md
```

Validate every finding locally. A `changes_requested` verdict can lead to cycle 2; cycle 3 is reserved for a distinct remaining issue. Never exceed three cycles.
