# Two-Level Skill Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add Git-shared skill defaults and machine-local enable/disable/reset overrides without deleting sources or treating intentional OFF state as drift.

**Architecture:** Extend each manifest skill asset with a backward-compatible `enabled` default and load a separate local TOML preference file under `CODEX_HOME`. One effective-state function feeds plan, status, apply, doctor, and the new `skill` CLI so all surfaces agree. Toggle commands snapshot, validate, atomically update preferences, and reconcile only one matching symlink.

**Tech Stack:** Python 3.11+, `tomllib`, existing `tomlkit`-backed harness runner, `unittest`, TOML, symlinks.

---

## File structure

| File | Responsibility |
|---|---|
| `manifest.toml` | Harness version, preference path, and Git-shared per-skill default. |
| `tools/harness.py` | Parse activation state, compute effective state, report/reconcile links, expose CLI. |
| `tests/test_harness.py` | Temporary-home integration coverage for precedence, safety, and recovery. |
| `tests/test_sources.py` | Static manifest/document contract. |
| `README.md` | Command discovery. |
| `docs/user-guide.md` | Repository-default and local-override operating procedures. |
| `docs/operations.md` | Daily toggle and recovery notes. |

### Task 1: Parse repository defaults and local preferences

**Files:**

- Modify: `manifest.toml`
- Modify: `tools/harness.py`
- Test: `tests/test_harness.py`

- [x] **Step 1: Write failing preference/default tests**

Add tests that apply a temporary manifest with `enabled = false`, assert that the selected skill link stays absent, and assert that malformed preferences fail with exit 2:

```python
def test_manifest_can_disable_a_skill_by_default(self):
    manifest = self.home / "manifest.toml"
    manifest.write_text((ROOT / "manifest.toml").read_text().replace(
        'id = "skill-parallel-review"',
        'id = "skill-parallel-review"\nenabled = false',
        1,
    ))
    self.run_cli("--manifest", str(manifest), "apply", "--yes")
    self.assertFalse((self.home / ".agents/skills/parallel-review").exists())
    self.assertTrue((self.home / ".agents/skills/dual-loop-review").is_symlink())

def test_invalid_local_skill_preferences_fail_closed(self):
    preferences = self.codex_home / ".codex-helper/preferences.toml"
    preferences.parent.mkdir(parents=True)
    preferences.write_text(
        'schema_version = 1\n[skills]\nenabled = ["skill-parallel-review"]\n'
        'disabled = ["skill-parallel-review"]\n'
    )
    result = self.run_cli("plan", "--json", check=False)
    self.assertEqual(2, result.returncode)
```

- [x] **Step 2: Run the new tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_harness.HarnessTests.test_manifest_can_disable_a_skill_by_default \
  tests.test_harness.HarnessTests.test_invalid_local_skill_preferences_fail_closed -v
```

Expected: failure because `Asset` has no default state and preferences are not loaded.

- [x] **Step 3: Add the minimal state model**

Add `enabled: bool` to `Asset`, `preferences_path: Path` to `Context`, and parse `item.get("enabled", True)` with a boolean type check. Add:

```python
@dataclass(frozen=True)
class SkillPreferences:
    enabled: frozenset[str]
    disabled: frozenset[str]

def read_skill_preferences(context: Context) -> SkillPreferences:
    if not context.preferences_path.exists():
        return SkillPreferences(frozenset(), frozenset())
    data = tomllib.loads(context.preferences_path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported skill preferences schema_version")
    skills = data.get("skills", {})
    enabled = frozenset(skills.get("enabled", []))
    disabled = frozenset(skills.get("disabled", []))
    if enabled & disabled:
        raise ValueError("skill preference cannot be both enabled and disabled")
    known = {asset.id for asset in context.assets if asset.category == "skills"}
    if not enabled | disabled <= known:
        raise ValueError("unknown or non-skill asset in skill preferences")
    return SkillPreferences(enabled, disabled)

def effective_enabled(asset: Asset, preferences: SkillPreferences) -> bool:
    if asset.category != "skills":
        return True
    if asset.id in preferences.enabled:
        return True
    if asset.id in preferences.disabled:
        return False
    return asset.enabled
```

Add `preferences = "${CODEX_HOME:-$HOME/.codex}/.codex-helper/preferences.toml"` under `[config]` and bump `harness_version` to `0.2.0`.

- [x] **Step 4: Run the focused tests and verify GREEN**

Run the Step 2 command. Expected: both pass.

### Task 2: Make all status and apply paths activation-aware

**Files:**

- Modify: `tools/harness.py`
- Test: `tests/test_harness.py`

- [x] **Step 1: Write failing steady-state and drift tests**

Add tests proving an intentional disabled target is healthy, a manifest-default OFF link is removed by apply, and a manually removed enabled link remains drift:

```python
def test_disabled_skill_is_healthy_but_manual_unlink_is_drift(self):
    self.run_cli("apply", "--yes")
    self.run_cli("skill", "disable", "parallel-review", "--json")
    status = self.run_cli("status", "--json")
    item = next(x for x in json.loads(status.stdout)["assets"]
                if x["id"] == "skill-parallel-review")
    self.assertEqual("disabled", item["status"])
    link = self.home / ".agents/skills/dual-loop-review"
    link.unlink()
    self.assertEqual(1, self.run_cli("status", "--json", check=False).returncode)
```

- [x] **Step 2: Run the test and verify RED**

Expected: parser rejects `skill` and status cannot represent disabled.

- [x] **Step 3: Implement activation-aware inspection and apply**

Change `inspect_asset(asset, enabled=True)` so absent+disabled is `disabled`, matching-link+disabled is `pending-disable`, and foreign occupancy is `conflict`. Treat only `current` and `disabled` as healthy in `command_plan`. In `command_apply`, remove a disabled asset only when `_link_matches` succeeds and create links only for enabled assets.

Include `default_enabled`, `local_override`, and `effective_enabled` in skill asset records. Include `context.preferences_path` in snapshot targets.

- [x] **Step 4: Run the focused test and existing apply tests**

Run:

```bash
python3 -m unittest tests.test_harness.HarnessTests.test_disabled_skill_is_healthy_but_manual_unlink_is_drift tests.test_harness.HarnessTests.test_apply_is_idempotent_and_preserves_unmanaged_entries -v
```

Expected: pass.

### Task 3: Add local skill enable, disable, reset, list, and status commands

**Files:**

- Modify: `tools/harness.py`
- Test: `tests/test_harness.py`

- [x] **Step 1: Write failing CLI lifecycle and conflict tests**

Add one lifecycle test and one refusal test:

```python
def test_local_skill_override_lifecycle(self):
    self.run_cli("apply", "--yes")
    disabled = json.loads(self.run_cli(
        "skill", "disable", "parallel-review", "--json"
    ).stdout)
    self.assertFalse(disabled["effective_enabled"])
    self.assertFalse((self.home / ".agents/skills/parallel-review").exists())
    enabled = json.loads(self.run_cli(
        "skill", "enable", "parallel-review", "--json"
    ).stdout)
    self.assertTrue(enabled["effective_enabled"])
    self.assertTrue((self.home / ".agents/skills/parallel-review").is_symlink())
    reset = json.loads(self.run_cli(
        "skill", "reset", "parallel-review", "--json"
    ).stdout)
    self.assertIsNone(reset["local_override"])

def test_skill_toggle_never_replaces_conflict(self):
    target = self.home / ".agents/skills/parallel-review"
    target.parent.mkdir(parents=True)
    target.write_text("foreign")
    result = self.run_cli("skill", "disable", "parallel-review", "--json", check=False)
    self.assertEqual(3, result.returncode)
    self.assertEqual("foreign", target.read_text())
    self.assertFalse((self.codex_home / ".codex-helper/preferences.toml").exists())
```

- [x] **Step 2: Run and verify RED**

Expected: `skill` is not a valid command.

- [x] **Step 3: Implement deterministic preferences and toggle transaction**

Add `resolve_skill`, `write_skill_preferences`, `skill_record`, `command_skill_list`, `command_skill_status`, and `command_skill_set`. TOML output must be deterministic:

```python
def skill_preferences_text(preferences: SkillPreferences) -> str:
    enabled = ", ".join(json.dumps(item) for item in sorted(preferences.enabled))
    disabled = ", ".join(json.dumps(item) for item in sorted(preferences.disabled))
    return (
        "schema_version = 1\n\n[skills]\n"
        f"enabled = [{enabled}]\n"
        f"disabled = [{disabled}]\n"
    )
```

`command_skill_set` must validate the current target, snapshot, atomically write preferences, reconcile only the chosen link, and restore the receipt on any exception. `reset` removes both override entries.

Add nested argparse subcommands for `skill list`, `skill status`, `skill enable`, `skill disable`, and `skill reset`; every subcommand supports `--json`.

- [x] **Step 4: Run lifecycle and conflict tests and verify GREEN**

Run the tests added in Step 1. Expected: pass.

### Task 4: Integrate doctor, docs, and version contracts

**Files:**

- Modify: `tests/test_sources.py`
- Modify: `README.md`
- Modify: `docs/user-guide.md`
- Modify: `docs/operations.md`
- Modify: `tools/harness.py`
- Modify: `manifest.toml`

- [x] **Step 1: Write failing documentation and doctor assertions**

Assert the README and user guide contain the five skill commands, local preference path, precedence, and new version. Extend doctor coverage to apply, disable, and still return healthy.

- [x] **Step 2: Run and verify RED**

Run:

```bash
python3 -m unittest tests.test_sources tests.test_harness.HarnessTests.test_doctor_passes_for_sources_and_applied_temp_home -v
```

Expected: documentation assertions fail.

- [x] **Step 3: Update operator surfaces**

Document both workflows:

```bash
# Git-shared default
# edit manifest skill enabled=false, then:
codex-harness plan
codex-harness apply --yes

# This machine only
codex-harness skill disable parallel-review
codex-harness skill enable parallel-review
codex-harness skill reset parallel-review
```

Update doctor so preferences parse/validate as part of the manifest/state health check and disabled skills count as healthy links.

- [x] **Step 4: Run source and doctor tests and verify GREEN**

Run the Step 2 command. Expected: pass.

### Task 5: Full verification and real-machine smoke

**Files:**

- Verify all modified files

- [x] **Step 1: Run the complete suite**

```bash
./tools/run-tests
git diff --check
```

Expected: all tests pass and no whitespace errors.

- [x] **Step 2: Verify the real plan before mutation**

```bash
codex-harness plan --json
codex-harness skill status parallel-review --json
```

Expected: no unexpected changes and effective state enabled.

- [x] **Step 3: Smoke local disable and health**

```bash
codex-harness skill disable parallel-review --json
codex-harness status --json
codex-harness doctor --json
```

Expected: skill status `disabled`, overall status exit 0, doctor healthy.

- [x] **Step 4: Reset and prove final convergence**

```bash
codex-harness skill reset parallel-review --json
codex-harness plan --json
codex-harness doctor --json
```

Expected: local override absent, link current, plan changes empty, doctor healthy.

- [x] **Step 5: Commit the implementation**

```bash
git add manifest.toml tools/harness.py tests README.md docs
git commit -m "feat: add two-level skill activation"
```
