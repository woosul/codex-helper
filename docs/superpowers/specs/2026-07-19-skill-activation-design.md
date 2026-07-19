# Skill Activation Design

## Goal

Allow every manifest-managed skill to keep its source in this repository while choosing activation at two independent scopes:

1. a Git-shared repository default; and
2. an explicit machine-local override.

Activation and deactivation change only the individual managed skill symlink. They never delete the source, mutate an undeclared skill, or rewrite unrelated Codex state.

## Success criteria

- A skill asset may declare `enabled = true` or `enabled = false` in `manifest.toml`; omission means `true` for backward compatibility.
- `codex-harness apply` creates links only for effectively enabled skills and removes only matching managed links for effectively disabled skills.
- `codex-harness skill enable|disable|reset NAME` manages a machine-local choice and immediately reconciles that one link.
- `reset` removes the local override and returns to the repository default.
- `skill list` and `skill status` show repository default, local override, effective state, and link state.
- `plan`, `status`, `inventory`, and `doctor` treat an intentionally absent disabled link as healthy, while a manually removed enabled link remains drift.
- Conflicting files or foreign links are never overwritten by a skill toggle.
- Snapshots include the local preference file so interrupted mutations and explicit restores are recoverable.
- Only repository defaults travel through Git. Local overrides remain outside the repository and are not copied to another machine.

## State model and precedence

Each skill has three inputs:

- `default_enabled`: the manifest `enabled` value, defaulting to `true`;
- `local_override`: `enabled`, `disabled`, or absent;
- `effective_enabled`: the local override when present, otherwise the manifest default.

The local preference file is `${CODEX_HOME}/.codex-helper/preferences.toml`:

```toml
schema_version = 1

[skills]
enabled = ["skill-example"]
disabled = ["skill-parallel-review"]
```

The same asset ID may not appear in both lists. Unknown IDs and non-skill asset IDs are errors so stale or misspelled preferences cannot silently affect state.

## CLI contract

```text
codex-harness skill list [--json]
codex-harness skill status NAME [--json]
codex-harness skill enable NAME [--json]
codex-harness skill disable NAME [--json]
codex-harness skill reset NAME [--json]
```

`NAME` accepts the canonical asset ID such as `skill-parallel-review` or its unambiguous short name `parallel-review`.

`enable`, `disable`, and `reset` are narrow, reversible operations. Before mutation they validate the target. A missing target or a matching managed symlink is safe; a regular file, directory, or foreign symlink returns the conflict exit code without changing preferences or the target.

## Link states

- `current`: effectively enabled and linked to the declared source.
- `disabled`: effectively disabled and the target is absent.
- `missing`, `broken`, or `drifted`: effectively enabled but not correctly linked.
- `pending-disable`: effectively disabled but the matching managed link still exists; `apply` removes it.
- `conflict`: the target is occupied by an unowned object in either effective state.

Only `current` and `disabled` are healthy steady states.

## Repository default workflow

To share activation across machines, edit only the skill stanza:

```toml
[[assets]]
id = "skill-parallel-review"
enabled = false
```

Then run `plan`, `apply --yes`, `doctor`, and commit the manifest change. A machine with an explicit local `enabled` override remains enabled because local intent has higher precedence; `skill reset parallel-review` returns it to the new Git default.

## Machine-local workflow

Use `skill disable NAME` to unlink one skill only on the current machine. Use `skill enable NAME` to force it on even when the repository default is off. Use `skill reset NAME` to remove the local decision. These commands update `preferences.toml` atomically and reconcile only that asset.

Codex discovers skills when a new task starts. Existing tasks may retain instructions already loaded into their context, so operators should start a new task after toggling.

## Safety and recovery

- Skill toggles never accept `--yes` and never replace conflicts.
- Matching-link checks use resolved source paths, including relative symlinks.
- Preferences are written atomically with mode `0600`.
- Snapshot receipts include the preference path.
- A toggle failure restores both the target and preferences from its snapshot.
- `unlink` removes harness-owned links but preserves machine-local preferences for a later reinstall.

## Testing

Temporary-home integration tests cover:

- omitted and explicit manifest defaults;
- local enable, disable, and reset precedence;
- stable list/status JSON fields;
- apply idempotence for both healthy states;
- manual unlink remaining drift;
- conflict refusal without preference mutation;
- snapshot restoration of the preference file;
- doctor health with an intentionally disabled skill.

The real-machine smoke toggles one managed sample skill off, checks status and doctor, resets it to the repository default, and confirms the final plan is empty.
