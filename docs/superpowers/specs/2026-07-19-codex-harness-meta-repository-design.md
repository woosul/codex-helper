# Codex Harness Meta Repository Design

**Date:** 2026-07-19  
**Status:** Approved direction; revision pending review
**Scope:** Personal, cross-machine Codex CLI and desktop harness management

## 1. Intent

Turn `codex-helper` into the sole source repository for Denny's Codex harness. A separate Claude harness may inform the one-time migration, but it is not a runtime, maintenance, documentation, or symlink dependency. After migration succeeds, Codex must not read, search, diff, execute, or modify that sibling repository.

The Codex harness must make a new machine easy to connect, keep static global guidance and reusable capabilities under Git, preserve Codex-owned runtime state, and make drift visible before it becomes a broken setup.

The design deliberately follows Codex's native extension surfaces:

- `~/.codex/AGENTS.md` for always-on personal guidance.
- `~/.codex/config.toml` for durable user settings.
- `~/.codex/agents/*.toml` for custom subagent roles.
- `$HOME/.agents/skills/*` for user-scoped filesystem skills.
- `~/.codex/rules/*.rules` for command policy.
- `~/.codex/<name>.config.toml` for selectable profiles.

## 2. Goals and success criteria

### Goals

1. Manage the original copies of Codex-specific global guidance, stable configuration, agents, profiles, rules, skills, and utilities in Git.
2. Rewire every managed static entry individually so unmanaged and externally injected entries survive.
3. Merge stable configuration into a real `~/.codex/config.toml` while preserving Codex-owned and machine-local runtime state.
4. Bootstrap another machine from a clone with one manifest-driven command sequence.
5. Report the installed inventory, source versions, link health, configuration drift, and unmanaged entries.
6. Install two practical Codex-native workflow samples: native parallel review and bounded internal/external review loops.
7. Preserve the Karpathy four principles as concise, always-on global policy.

### Acceptance criteria

| ID | Criterion | Verification |
|---|---|---|
| AC-01 | A fresh clone can preview and apply the harness on another macOS machine without editing repository paths into source files. | Temporary `HOME` bootstrap test followed by `plan`, `apply`, and `status` exit 0. |
| AC-02 | Re-running `apply` is idempotent. | Two consecutive applies produce the same managed files and links; second plan reports no changes. |
| AC-03 | Every static managed target is an individual symlink to a manifest-declared source. | `status --json` reports all declared links healthy and resolves each target under this repository. |
| AC-04 | Existing unrelated skills, rules, plugins, marketplaces, projects, desktop state, authentication, sessions, caches, and databases are preserved. | Fixture test seeds unmanaged entries and compares them byte-for-byte after apply. |
| AC-05 | Managed config additions, updates, and deletions are reflected in live config without deleting unmanaged keys. | Merge tests cover new key, changed key, removed formerly managed key, nested table, and array-of-table values. |
| AC-06 | Every operation that replaces or removes an existing entry or modifies live config creates a recoverable backup and uses atomic replacement. | Failure-injection test leaves the previous live state intact; restore test recovers the fixture. |
| AC-07 | Inventory and status commands report harness revision, host overlay, managed assets, source/version metadata, drift, broken links, and unmanaged entries. | CLI snapshot tests and exit-code tests pass. |
| AC-08 | The tracked root `AGENTS.md` is the global guidance source and contains all four Karpathy principles, fresh-evidence completion policy, and the harness-independence boundary. | Guidance contract test checks the canonical headings and `~/.codex/AGENTS.md` resolves to the repository root file. |
| AC-09 | Parallel review uses bounded, read-heavy native subagents and keeps final judgment with the root agent. | Skill/agent contract tests plus one opt-in smoke run. |
| AC-10 | External review runs in a fresh, ephemeral, read-only Codex process with a bounded cycle count and structured verdict. | Stub-runner unit test plus one opt-in live smoke run. |
| AC-11 | After migration, all active managed links and configuration are self-contained and no operational command consults the sibling Claude harness. | `doctor` proves every managed source resolves inside `codex-helper`; operational-source scan reports no sibling-repository path dependency. |

## 3. Non-goals

- Do not replace `CODEX_HOME` with the repository. Authentication, sessions, logs, caches, SQLite databases, downloaded plugins, and app state remain runtime-owned.
- Do not reproduce another harness's multi-version `current -> versions/V*` architecture. Git commits and tags version the Codex harness; manifest entries version individual external sources.
- Do not copy Claude-specific models, panels, hooks, commands, or orchestration policy.
- Do not take ownership of every pre-existing skill on the machine. Only manifest-declared assets are managed.
- Do not install an unbounded autonomous coding loop or use `--dangerously-bypass-approvals-and-sandbox`.
- Do not automatically pull, commit, push, or update third-party dependencies during routine `apply`.

## 4. Architecture

### 4.1 Repository layout

```text
codex-helper/
├── AGENTS.md
├── README.md
├── install.sh
├── manifest.toml
├── sources/
│   ├── config/
│   │   ├── base.toml
│   │   └── hosts/
│   │       ├── default.toml
│   │       └── rock.toml
│   ├── profiles/
│   │   ├── deep-review.config.toml
│   │   └── fast-scan.config.toml
│   ├── agents/
│   │   ├── scanner.toml
│   │   ├── reviewer.toml
│   │   └── verifier.toml
│   ├── rules/
│   │   └── codex-helper.rules
│   └── skills/
│       ├── parallel-review/
│       │   └── SKILL.md
│       └── dual-loop-review/
│           ├── SKILL.md
│           ├── references/
│           └── schemas/
├── bin/
│   ├── codex-harness
│   └── codex-external-review
├── tools/
│   ├── harness.py
│   └── merge_config.py
├── tests/
│   ├── fixtures/
│   ├── test_harness.py
│   └── test_merge_config.py
└── docs/
    ├── architecture.md
    ├── operations.md
    ├── cross-machine-bootstrap.md
    ├── sources.md
    └── superpowers/
```

Each file has one responsibility:

- `manifest.toml` declares ownership and mappings; it contains no mutable host state.
- `install.sh` is the cross-machine first-run wrapper; it delegates all logic to the tested harness CLI.
- `sources/` contains Git-tracked originals.
- `bin/` contains stable user entry points.
- `tools/` implements manifest parsing, planning, merge, backup, restore, health, and inventory.
- `tests/` runs against temporary homes and never modifies the real user environment.
- `docs/` explains architecture, bootstrap, maintenance, and source attribution.

### 4.2 Ownership boundary

#### Individually symlinked static assets

| Live target | Repository source |
|---|---|
| `~/.codex/AGENTS.md` | `AGENTS.md` |
| `~/.codex/agents/scanner.toml` | `sources/agents/scanner.toml` |
| `~/.codex/agents/reviewer.toml` | `sources/agents/reviewer.toml` |
| `~/.codex/agents/verifier.toml` | `sources/agents/verifier.toml` |
| `$HOME/.agents/skills/parallel-review` | `sources/skills/parallel-review` |
| `$HOME/.agents/skills/dual-loop-review` | `sources/skills/dual-loop-review` |
| `~/.codex/rules/codex-helper.rules` | `sources/rules/codex-helper.rules` |
| `~/.codex/deep-review.config.toml` | `sources/profiles/deep-review.config.toml` |
| `~/.codex/fast-scan.config.toml` | `sources/profiles/fast-scan.config.toml` |
| `~/.local/bin/codex-harness` | `bin/codex-harness` |
| `~/.local/bin/codex-external-review` | `bin/codex-external-review` |

The rewire operation may replace only a target declared in the manifest. A conflicting real file or link with a different owner is backed up and requires an explicit `apply`; it is never removed by `plan` or `status`.

#### Merge-managed live file

`~/.codex/config.toml` remains a real file. The effective managed overlay is:

```text
deep_merge(sources/config/base.toml, selected_host_overlay)
```

`apply` records the exact managed key paths and hashes in `~/.codex/.codex-helper/state.json`. On the next apply it:

1. Loads the live file and prior state.
2. Removes only key paths previously owned by this harness.
3. Deep-merges the current managed overlay.
4. Validates the resulting TOML.
5. Atomically replaces the live file.
6. Writes the new state only after successful replacement.

This supports intentional deletion of a managed key without treating all live configuration as repository-owned.

#### Runtime-owned and preserved

The harness never links, copies, or deletes these paths:

- `auth.json`, history, sessions, archived sessions, logs, caches, SQLite files, installation ID, and generated media.
- Plugin cache and installed plugin directories.
- `rules/default.rules`, because Codex writes interactive allow-list choices there.
- Manifest-unlisted skills or symlinks in `$HOME/.agents/skills` and `~/.codex/skills`.

The config merge also preserves unowned live keys. Initial repository sources exclude runtime catalogs such as `plugins`, `marketplaces`, `projects`, `desktop`, and `tui.model_availability_nux`. Stable user preferences and explicitly selected MCP definitions may be adopted into `base.toml` or a host overlay after reviewing them for secrets and machine-specific paths.

### 4.3 Manifest

`manifest.toml` is the single mapping catalog. It uses repository-relative sources and variable-based targets so the same checkout works on different machines.

Required top-level metadata:

```toml
schema_version = 1
harness_version = "0.1.0"
minimum_codex_version = "0.144.5"

[paths]
codex_home = "${CODEX_HOME:-$HOME/.codex}"
user_skills = "$HOME/.agents/skills"
user_bin = "$HOME/.local/bin"
```

Each asset entry declares:

- stable `id`
- `kind`: `symlink`, `config-overlay`, or `utility`
- repository-relative `source`
- variable-based `target`
- `scope`: `global` or `host`
- `version`
- optional `requires`
- optional upstream URL, pinned revision, license, and attribution

Unknown schema versions fail closed. Duplicate IDs, duplicate targets, sources outside the repository, targets outside approved roots, unresolved variables, and missing required files fail during `plan` before any mutation.

### 4.4 Host selection and cross-machine bootstrap

Host selection order:

1. `--host NAME`
2. `CODEX_HELPER_HOST`
3. normalized `hostname -s` when `sources/config/hosts/<host>.toml` exists
4. `sources/config/hosts/default.toml`

Host overlays contain only non-secret machine differences such as executable paths, local MCP commands, and trusted project paths. Secrets stay in environment variables or Codex-supported credential stores. A gitignored `sources/config/hosts/<host>.local.toml` may be loaded last when explicitly enabled; it is reported as local-only by `inventory`.

Bootstrap on another machine:

```bash
git clone <repository-url> ~/Project/codex-helper
cd ~/Project/codex-helper
./install.sh --host <name>
./bin/codex-harness doctor
```

`install.sh` checks prerequisites, runs `bootstrap` and `plan`, then asks before delegating to `apply`. `bootstrap` creates missing parent directories but does not mutate an existing Codex entry point. The installer prints required manual steps, including adding `$HOME/.local/bin` to `PATH` when needed and restarting Codex after configuration changes.

To create a tracked overlay for a newly named machine, run `codex-harness host init <name>`, review the generated non-secret skeleton, and commit it. Machine-only values can instead go into the explicitly enabled gitignored local overlay.

Pulling updates on an existing machine uses:

```bash
git pull --ff-only
codex-harness plan
codex-harness apply
codex-harness doctor
```

The harness does not run `git pull` itself. This keeps repository updates separate from local configuration mutation and makes changes reviewable.

## 5. Global guidance: Karpathy four principles

The tracked root `AGENTS.md` is both this repository's project guidance and the canonical global source linked at `~/.codex/AGENTS.md`. It contains:

1. **Think Before Coding** — state assumptions, expose ambiguity, present meaningful trade-offs, and stop when an unresolved choice would materially change the result.
2. **Simplicity First** — implement the smallest solution that satisfies the request; no speculative abstractions, options, or edge-case machinery.
3. **Surgical Changes** — change only lines traceable to the request, preserve local style, and remove only residue created by the current change.
4. **Goal-Driven Execution** — translate work into measurable acceptance criteria and loop until fresh evidence satisfies them.

Codex-specific additions remain short:

- Use skills only when their trigger matches.
- Parallelize independent read-heavy work; coordinate writes through the root agent or isolated worktrees.
- Do not claim completion without fresh test/build/behavior evidence.
- Prefer global `AGENTS.md` for durable behavior, skills for reusable workflows, agents for bounded roles, and rules for command policy.
- Treat `codex-helper` as the only Codex harness source after migration; never inspect or invoke the sibling Claude harness repository.

The file contains no Claude model names, Claude panel topology, absolute sibling-repository path, or instructions that require the sibling repository. This boundary applies to future Codex sessions even when historical comparison appears convenient.

## 6. Installed workflow samples

### 6.1 Native parallel review

The `parallel-review` skill is an explicitly triggered, read-heavy review workflow. It asks the root agent to spawn bounded native subagents, wait for all requested results, and consolidate evidence.

Roles:

- `scanner`: fast repository exploration, affected-path mapping, and fact collection; read-only.
- `reviewer`: correctness, security, regressions, and maintainability review; read-only.
- `verifier`: test coverage, acceptance-criteria mapping, and fresh verification evidence; read-only.

Defaults in managed config:

```toml
[agents]
max_threads = 4
max_depth = 1
```

The skill does not allow subagents to commit, push, or concurrently edit the same checkout. The root agent owns requirements, synthesis, mutations, and the final verdict. This follows the current Codex guidance to begin parallelization with exploration, tests, triage, and summarization rather than write-heavy fan-out.

### 6.2 Bounded dual-loop review

The `dual-loop-review` skill separates two feedback loops:

1. **Internal loop:** the active agent defines acceptance criteria, makes the minimal change, runs relevant checks, reads failures, corrects the change, and reruns checks before requesting review.
2. **External loop:** `codex-external-review` launches a fresh Codex process with `--ephemeral`, `--sandbox read-only`, a review profile, and a JSON output schema. It reviews the current diff and verification evidence without modifying the checkout.

The external verdict is one of `pass`, `changes_requested`, or `blocked`, with findings, file references, and requested evidence. `changes_requested` returns control to the active agent for one bounded correction cycle. The default maximum is two external cycles and the hard maximum is three. The workflow stops on repeated findings, missing authority, unavailable tests, or exhausted cycles; it never converts uncertainty into success.

Persistent learning is deliberate rather than automatic. The workflow may propose an `AGENTS.md`, skill, or rule update when a failure pattern repeats, but it changes global policy only with user authorization.

This adapts the community's inner/outer loop distinction and Ralph's fresh-context, file/Git-memory pattern without installing an unbounded autonomous runner.

## 7. Command surface

`codex-harness` provides the following commands:

| Command | Purpose | Mutates state? |
|---|---|---:|
| `plan` | Show exact link, config, directory, conflict, and backup actions. | No |
| `apply` | Back up conflicts, create/update declared links, merge config, and write state atomically. | Yes |
| `status` | Show concise health, drift, and unmanaged summary. | No |
| `status --json` | Emit machine-readable status for scripts and cross-machine comparison. | No |
| `inventory` | List harness, asset, skill, utility, profile, agent, and upstream versions. | No |
| `inventory --json` | Emit the inventory contract as JSON. | No |
| `list --kind KIND` | Filter inventory to `skills`, `agents`, `profiles`, `rules`, or `utilities`. | No |
| `doctor` | Validate manifest, TOML, links, skill metadata, agent schema, prerequisites, and Codex compatibility. | No |
| `bootstrap` | Check prerequisites and create missing parent directories; print the next commands. | Limited |
| `host init NAME` | Create a non-secret host-overlay skeleton without changing the live Codex config. | Repository only |
| `snapshot` | Back up all harness-owned targets plus current live config and state. | Yes |
| `restore ID` | Preview, then restore a named snapshot after confirmation or `--yes`. | Yes |
| `unlink` | Preview removal of only harness-owned links and managed config keys; preserve source files. | Yes |
| `version [ASSET_ID]` | Print harness version, Git revision, schema, detected Codex version, or one asset's source/version metadata. | No |

Exit codes are stable:

- `0`: healthy or operation completed
- `1`: drift or validation failure
- `2`: invalid usage or manifest
- `3`: conflict requiring user action
- `4`: partial operation safely rolled back

Human output is concise; JSON output contains no secrets or raw config values.

## 8. Version and source management

- The repository's Git history is the source of truth for owned assets.
- Release tags use `vMAJOR.MINOR.PATCH`; `manifest.toml` carries the matching harness version.
- Every owned skill, agent, profile, rule, and utility has an independent semantic version in the manifest.
- Third-party material is not copied silently. A source entry records upstream URL, pinned commit or release, license, local adaptation notes, and last-reviewed date.
- `inventory` compares the installed target to the manifest source and reports `current`, `drifted`, `missing`, `broken`, or `unmanaged`.
- `sources.md` attributes OpenAI documentation and community patterns. It distinguishes ideas adapted into local code from vendored code.
- Updating a third-party source is a separate reviewed change. Routine `apply` never downloads code.

No version parity convention or frozen upstream submodule is required for the initial harness. A vendored dependency may use a pinned Git submodule later only when copying or adapting a small local implementation is less maintainable.

## 9. Safety, backup, and recovery

Before mutation, the tool resolves and validates every path. Approved target roots are limited to:

- resolved `CODEX_HOME`
- `$HOME/.agents/skills`
- `$HOME/.local/bin`
- the harness-owned backup/state directory under `CODEX_HOME`

It rejects repository root, home root, empty paths, unresolved variables, parent traversal, and targets outside the allowlist.

Backups live under:

```text
~/.codex/backups/codex-helper/<UTC timestamp>/
```

Each backup includes a receipt with source path, target path, target type, link destination or file hash, harness Git revision, host, and restore order. File replacement uses a temporary sibling followed by `os.replace`. Link replacement uses a temporary link followed by rename. If a step fails, the transaction restores completed steps in reverse order and leaves a failure receipt.

Config and status output redact values for keys matching token, secret, password, credential, auth, or key patterns. Source files containing a suspected secret fail `doctor` unless the value is an environment-variable reference or explicitly allowlisted by key name.

## 10. Testing and verification

The implementation uses Python 3.11+ with `tomlkit` pinned through a `uv` script environment. `tomlkit` preserves TOML structure while the state file provides explicit ownership. Shell entry points contain only path resolution and process launch.

Tests run under temporary `HOME` and `CODEX_HOME` values and cover:

- manifest schema and path validation
- default and explicit host selection
- first apply and no-op second apply
- individual link creation and repair
- preservation of unmanaged real directories and external symlinks
- config add/change/delete semantics
- preservation of runtime-owned nested tables and arrays of tables
- interrupted config/link replacement and rollback
- snapshot and restore
- inventory/status JSON schemas and exit codes
- Karpathy guidance contract
- skill frontmatter and referenced-file existence
- custom agent required fields and read-only sandbox policy
- external review argument construction, cycle bounds, and JSON verdict parsing

Verification sequence:

1. Unit and integration tests in a temporary home.
2. `codex-harness doctor --root <temporary-home>`.
3. Dry-run import of the current machine's relevant entry points with values redacted in logs.
4. `plan` against the real home and manual review of every proposed target.
5. `snapshot`, then `apply` with required filesystem approval.
6. Fresh `status`, `inventory`, `doctor`, and second `plan` proving no drift.
7. Confirm every active managed target resolves inside `codex-helper`, then enable the permanent no-inspection boundary for future sessions.

Live model calls are opt-in tests because they consume usage. One final smoke test runs native subagent review, and one runs the external reviewer on a harmless fixture repository.

## 11. Migration of the current machine

The current observed state includes:

- `~/.codex/AGENTS.md` linked outside this repository to the legacy global guidance source.
- `~/.codex/config.toml` as a real file with user preferences plus Codex-managed plugin, marketplace, project, desktop, and UI state.
- `~/.codex/rules/default.rules` as a real runtime-managed file.
- A mixture of real directories and external links under existing skill locations.
- Codex CLI `0.144.5` at design time.

Migration steps:

1. Create and track the root `AGENTS.md`, adapting only the Karpathy four principles plus concise Codex-native and harness-independence guidance.
2. Extract stable user preferences into `base.toml` and machine-specific, non-secret MCP/path settings into `hosts/rock.toml`.
3. Leave runtime catalogs and all undeclared files unowned.
4. Add only the two new sample skills and three custom agents to the manifest.
5. Preview the replacement of the existing global `AGENTS.md` link and preserve its previous destination in the backup receipt.
6. Apply the new root `AGENTS.md` link and verify the self-contained Codex setup. After that verification, no later command, test, status check, or maintenance workflow may inspect the sibling Claude harness.

## 12. Rejected alternatives

### Repository as `CODEX_HOME`

Rejected because it mixes Git-managed policy with credentials, databases, sessions, logs, caches, and app-managed state.

### Whole-file `config.toml` symlink

Rejected because the desktop app and CLI update user configuration. A symlink would dirty the source repository and make runtime state portable when it should remain local.

### Whole skill-directory symlink

Rejected because installers and other runtimes inject skills independently. Entry-level links preserve those ownership boundaries.

### Full Claude multi-version clone

Rejected because Codex already provides config layers, standalone agent files, user skills, profiles, plugins, and runtime state with different ownership semantics. Git tags plus an asset manifest are sufficient until a concrete need for switchable full harness versions appears.

### Unbounded Ralph-style automation

Rejected for the initial harness because unattended write loops compound failures and complicate approvals. The installed adaptation keeps fresh-context external review but bounds cycles and holds writes in the active, supervised agent.

## 13. Sources

- OpenAI, [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- OpenAI, [Build skills](https://learn.chatgpt.com/docs/build-skills)
- OpenAI, [Advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)
- OpenAI, [Rules](https://learn.chatgpt.com/docs/agent-configuration/rules)
- Phil Schmid, [Agents: Inner Loop vs Outer Loop](https://www.philschmid.de/inner-loop-vs-outer-loop)
- snarktank, [Ralph](https://github.com/snarktank/ralph)

## 14. Ordered follow-up research

Only after AC-01 through AC-11 pass on the real machine:

1. Research how Codex should use external review-only agents for plan and implementation review. Start with current official Codex documentation, then compare primary community implementations. Do not use the sibling Claude harness as a source.
2. After the external-agent report, discover and recommend skills for specification-driven development (SDD) and test-driven development (TDD). Evaluate trigger quality, maintenance activity, license, Codex compatibility, and overlap with the installed dual-loop workflow before recommending installation.

These are follow-up research deliverables, not prerequisites for the initial harness implementation or permission to install additional third-party code.
