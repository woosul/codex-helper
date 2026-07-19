# Codex Harness Meta Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and safely apply a self-contained, cross-machine Codex harness that owns global guidance, stable configuration overlays, custom agents, profiles, rules, skills, utilities, inventory, backups, and health checks.

**Architecture:** Git owns static source assets declared in `manifest.toml`; every static live target is an entry-level symlink, while `~/.codex/config.toml` remains a real file updated by an ownership-aware TOML merge. A Python CLI performs read-only planning and status plus transactional apply/restore operations, and thin shell wrappers provide cross-machine installation and external review entry points.

**Tech Stack:** Python 3.11+, standard-library `unittest`, `tomlkit==0.13.3` via `uv run --with`, Bash/POSIX shell wrappers, TOML, JSON Schema, Git, Codex CLI 0.144.5+.

---

## Scope and file map

This plan implements AC-01 through AC-11 from `docs/superpowers/specs/2026-07-19-codex-harness-meta-repository-design.md`. Follow-up research about external non-Codex agents and SDD/TDD skill recommendations starts only after Task 10 passes on the real machine.

| File | Responsibility |
|---|---|
| `AGENTS.md` | Canonical global Codex policy and project maintenance rules. |
| `.gitignore` | Exclude host-local overlays, test artifacts, caches, and loop output. |
| `manifest.toml` | Single source for harness version, paths, config layers, and managed assets. |
| `sources/config/base.toml` | Stable cross-machine Codex preferences owned by Git. |
| `sources/config/hosts/default.toml` | Empty portable host fallback. |
| `sources/config/hosts/rock.toml` | Tracked non-secret settings for the current machine. |
| `sources/agents/*.toml` | Read-only scanner, reviewer, and verifier roles. |
| `sources/profiles/*.config.toml` | Deep-review and fast-scan CLI overlays. |
| `sources/rules/codex-helper.rules` | Allow policy for read-only harness inspection commands. |
| `sources/skills/parallel-review/` | Native bounded subagent review workflow. |
| `sources/skills/dual-loop-review/` | Internal verification plus fresh external Codex review workflow. |
| `tools/merge_config.py` | Ownership-aware TOML merge with managed-path deletion. |
| `tools/harness.py` | Manifest validation, planning, status, inventory, transactions, doctor, and external review. |
| `bin/codex-harness` | Stable `uv` launcher for `tools/harness.py`. |
| `bin/codex-external-review` | Stable alias for `codex-harness external-review`. |
| `install.sh` | First-run bootstrap, preview, confirmation, apply, and doctor. |
| `tools/run-tests` | Pinned test launcher. |
| `tests/test_sources.py` | Guidance, TOML, agent, profile, and rules contracts. |
| `tests/test_merge_config.py` | Config ownership and preservation behavior. |
| `tests/test_harness.py` | CLI, linking, backup, restore, drift, and doctor integration. |
| `tests/test_external_review.py` | External review command and verdict contract with a stub Codex executable. |
| `docs/architecture.md` | Ownership and data-flow explanation. |
| `docs/operations.md` | Daily plan/apply/status/restore workflow. |
| `docs/cross-machine-bootstrap.md` | New-machine and new-host procedure. |
| `docs/sources.md` | Official/community attribution and adaptation boundaries. |
| `README.md` | Concise entry point and command reference. |

## Task 1: Establish source contracts and global policy

**Files:**
- Create: `AGENTS.md`
- Create: `.gitignore`
- Create: `manifest.toml`
- Create: `sources/config/base.toml`
- Create: `sources/config/hosts/default.toml`
- Create: `sources/config/hosts/rock.toml`
- Create: `sources/agents/scanner.toml`
- Create: `sources/agents/reviewer.toml`
- Create: `sources/agents/verifier.toml`
- Create: `sources/profiles/deep-review.config.toml`
- Create: `sources/profiles/fast-scan.config.toml`
- Create: `sources/rules/codex-helper.rules`
- Create: `tests/test_sources.py`
- Create: `tools/run-tests`

- [ ] **Step 1: Write the failing source-contract test**

Create `tests/test_sources.py` with this contract:

```python
from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourceContractTests(unittest.TestCase):
    def test_global_guidance_contract(self):
        text = (ROOT / "AGENTS.md").read_text()
        for heading in (
            "Think Before Coding",
            "Simplicity First",
            "Surgical Changes",
            "Goal-Driven Execution",
            "Harness Independence",
        ):
            self.assertIn(heading, text)
        self.assertIn("fresh", text.lower())
        self.assertNotRegex(text, re.compile(r"/[^\n]*/claude-harness-helper"))

    def test_manifest_and_toml_sources_parse(self):
        paths = [
            ROOT / "manifest.toml",
            ROOT / "sources/config/base.toml",
            ROOT / "sources/config/hosts/default.toml",
            ROOT / "sources/config/hosts/rock.toml",
            ROOT / "sources/agents/scanner.toml",
            ROOT / "sources/agents/reviewer.toml",
            ROOT / "sources/agents/verifier.toml",
            ROOT / "sources/profiles/deep-review.config.toml",
            ROOT / "sources/profiles/fast-scan.config.toml",
        ]
        for path in paths:
            with self.subTest(path=path):
                tomllib.loads(path.read_text())

    def test_agents_are_named_and_read_only(self):
        for name in ("scanner", "reviewer", "verifier"):
            data = tomllib.loads((ROOT / f"sources/agents/{name}.toml").read_text())
            self.assertEqual(name, data["name"])
            self.assertEqual("read-only", data["sandbox_mode"])
            self.assertTrue(data["description"])
            self.assertTrue(data["developer_instructions"])

    def test_manifest_targets_are_unique(self):
        data = tomllib.loads((ROOT / "manifest.toml").read_text())
        assets = data["assets"]
        self.assertEqual(len(assets), len({asset["id"] for asset in assets}))
        self.assertEqual(len(assets), len({asset["target"] for asset in assets}))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
uv run --with tomlkit==0.13.3 python -m unittest tests.test_sources -v
```

Expected: `ERROR` for missing `AGENTS.md` or `manifest.toml`.

- [ ] **Step 3: Create the canonical `AGENTS.md`**

Use this exact structure, keeping the operational policy concise:

```markdown
# OpenAI Codex Global Instructions

These instructions are the personal default for Codex across repositories. More specific repository instructions may add constraints without weakening safety or verification.

## 1. Think Before Coding

- State material assumptions before implementation.
- When multiple interpretations would change the result, present the trade-off and ask.
- Prefer the simpler valid alternative and name unresolved uncertainty.

## 2. Simplicity First

- Implement only what the request requires.
- Do not add speculative abstractions, configuration, features, or impossible-scenario handling.
- If the solution can be substantially smaller without losing behavior, simplify it.

## 3. Surgical Changes

- Every changed line must trace to the request.
- Preserve existing style and avoid unrelated refactors or cleanup.
- Remove only imports, variables, files, or links made obsolete by the current change.

## 4. Goal-Driven Execution

- Translate work into measurable acceptance criteria before changing code.
- For bugs and behavior changes, establish a failing test or reproduction before the fix.
- Do not claim completion without fresh test, build, or behavior evidence from the final state.

## Codex Operating Rules

- Use `AGENTS.md` for durable behavior, skills for reusable workflows, custom agents for bounded roles, and rules for command policy.
- Parallelize independent read-heavy work; coordinate writes through the root agent or isolated worktrees.
- Preserve user changes and external tool-managed state unless the user explicitly places them in scope.

## Harness Independence

- `codex-helper` is the sole source repository for the Codex harness.
- Never read, search, diff, execute, or modify the sibling Claude harness repository.
- Managed Codex links must resolve inside `codex-helper`; runtime-owned Codex state remains outside Git.
```

- [ ] **Step 4: Create the initial manifest and stable config sources**

Create `manifest.toml`:

```toml
schema_version = 1
harness_version = "0.1.0"
minimum_codex_version = "0.144.5"

[paths]
codex_home = "${CODEX_HOME:-$HOME/.codex}"
user_skills = "$HOME/.agents/skills"
user_bin = "$HOME/.local/bin"

[config]
base = "sources/config/base.toml"
host_dir = "sources/config/hosts"
state = "${CODEX_HOME:-$HOME/.codex}/.codex-helper/state.json"
backups = "${CODEX_HOME:-$HOME/.codex}/backups/codex-helper"

[[assets]]
id = "global-agents"
kind = "symlink"
category = "guidance"
source = "AGENTS.md"
target = "${CODEX_HOME:-$HOME/.codex}/AGENTS.md"
scope = "global"
version = "1.0.0"

[[assets]]
id = "agent-scanner"
kind = "symlink"
category = "agents"
source = "sources/agents/scanner.toml"
target = "${CODEX_HOME:-$HOME/.codex}/agents/scanner.toml"
scope = "global"
version = "1.0.0"

[[assets]]
id = "agent-reviewer"
kind = "symlink"
category = "agents"
source = "sources/agents/reviewer.toml"
target = "${CODEX_HOME:-$HOME/.codex}/agents/reviewer.toml"
scope = "global"
version = "1.0.0"

[[assets]]
id = "agent-verifier"
kind = "symlink"
category = "agents"
source = "sources/agents/verifier.toml"
target = "${CODEX_HOME:-$HOME/.codex}/agents/verifier.toml"
scope = "global"
version = "1.0.0"

[[assets]]
id = "profile-deep-review"
kind = "symlink"
category = "profiles"
source = "sources/profiles/deep-review.config.toml"
target = "${CODEX_HOME:-$HOME/.codex}/deep-review.config.toml"
scope = "global"
version = "1.0.0"

[[assets]]
id = "profile-fast-scan"
kind = "symlink"
category = "profiles"
source = "sources/profiles/fast-scan.config.toml"
target = "${CODEX_HOME:-$HOME/.codex}/fast-scan.config.toml"
scope = "global"
version = "1.0.0"

[[assets]]
id = "rules-codex-helper"
kind = "symlink"
category = "rules"
source = "sources/rules/codex-helper.rules"
target = "${CODEX_HOME:-$HOME/.codex}/rules/codex-helper.rules"
scope = "global"
version = "1.0.0"
```

Create `sources/config/base.toml`:

```toml
personality = "pragmatic"
model = "gpt-5.6-sol"
model_reasoning_effort = "high"

[features]
multi_agent = true
rmcp_client = true
js_repl = false

[agents]
max_threads = 4
max_depth = 1
```

Create both host files with valid, non-secret TOML:

```toml
# Host-specific non-secret Codex settings belong here.
```

Do not copy `notify`, MCP server definitions, plugins, marketplaces, projects, desktop state, or UI-discovery state from the live config.

- [ ] **Step 5: Create agent, profile, and rules sources**

Create `sources/agents/scanner.toml`:

```toml
name = "scanner"
description = "Fast read-only repository exploration and affected-path mapping."
model = "gpt-5.6-terra"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
developer_instructions = """
Explore only the assigned question. Do not edit files, commit, push, or broaden scope.
Return distilled facts with file references, commands run, and explicit uncertainty.
"""
```

Create `sources/agents/reviewer.toml`:

```toml
name = "reviewer"
description = "Read-only owner-level review for correctness, security, regressions, and maintainability."
model = "gpt-5.6-sol"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = """
Review the requested change without editing it. Prioritize behavior regressions, security, test gaps, and requirement mismatches.
Report only actionable findings with severity, file references, evidence, and a concise verdict.
"""
```

Create `sources/agents/verifier.toml`:

```toml
name = "verifier"
description = "Read-only acceptance-criteria and fresh-evidence verifier."
model = "gpt-5.6-sol"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = """
Map each acceptance criterion to fresh test, build, or behavior evidence. Do not edit files.
Distinguish pass, fail, not run, and blocked; never infer a pass from static inspection alone.
"""
```

Create `sources/profiles/deep-review.config.toml`:

```toml
model = "gpt-5.6-sol"
model_reasoning_effort = "xhigh"
sandbox_mode = "read-only"
```

Create `sources/profiles/fast-scan.config.toml`:

```toml
model = "gpt-5.6-terra"
model_reasoning_effort = "medium"
sandbox_mode = "read-only"
```

Create `sources/rules/codex-helper.rules`:

```python
prefix_rule(
    pattern = ["codex-harness", ["plan", "status", "inventory", "list", "version", "doctor"]],
    decision = "allow",
    justification = "These Codex harness commands are read-only health and inventory checks.",
    match = [
        "codex-harness plan",
        "codex-harness status --json",
        "codex-harness inventory",
        "codex-harness doctor",
    ],
    not_match = [
        "codex-harness apply",
        "codex-harness restore latest",
        "codex-harness unlink",
    ],
)
```

- [ ] **Step 6: Add ignore rules and the pinned test launcher**

Create `.gitignore`:

```gitignore
__pycache__/
*.pyc
.codex-loop/
.coverage
sources/config/hosts/*.local.toml
!sources/config/hosts/default.toml
!sources/config/hosts/rock.toml
```

Create executable `tools/run-tests`:

```sh
#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec uv run --with tomlkit==0.13.3 python -m unittest discover -s "$ROOT/tests" -v
```

- [ ] **Step 7: Run the source contracts**

Run:

```bash
chmod +x tools/run-tests
./tools/run-tests
```

Expected: `Ran 4 tests ... OK`.

- [ ] **Step 8: Commit the source contracts**

```bash
git add AGENTS.md .gitignore manifest.toml sources tests/test_sources.py tools/run-tests
git commit -m "feat: define Codex harness sources"
```

## Task 2: Implement ownership-aware config merging

**Files:**
- Create: `tools/merge_config.py`
- Create: `tests/test_merge_config.py`

- [ ] **Step 1: Write failing merge tests**

Create `tests/test_merge_config.py`:

```python
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from merge_config import merge_config


class MergeConfigTests(unittest.TestCase):
    def test_add_change_delete_and_preserve(self):
        live = """
model = "old"
obsolete = true
[features]
multi_agent = false
[plugins.demo]
enabled = true
"""
        overlay = """
model = "new"
[features]
multi_agent = true
"""
        result = merge_config(
            live,
            overlay,
            previous_paths=(("model",), ("obsolete",), ("features", "multi_agent")),
        )
        self.assertIn('model = "new"', result.text)
        self.assertNotIn("obsolete", result.text)
        self.assertIn("multi_agent = true", result.text)
        self.assertIn("[plugins.demo]", result.text)
        self.assertIn("enabled = true", result.text)
        self.assertEqual(
            (("features", "multi_agent"), ("model",)),
            result.managed_paths,
        )

    def test_preserves_unmanaged_array_of_tables(self):
        live = """
[[skills.config]]
path = "/tmp/demo/SKILL.md"
enabled = false
"""
        result = merge_config(live, "[agents]\nmax_depth = 1\n", previous_paths=())
        self.assertIn("[[skills.config]]", result.text)
        self.assertIn('path = "/tmp/demo/SKILL.md"', result.text)
        self.assertIn("max_depth = 1", result.text)

    def test_invalid_toml_fails_before_output(self):
        with self.assertRaisesRegex(ValueError, "invalid live TOML"):
            merge_config("[broken", "model = \"x\"", previous_paths=())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the merge tests to verify RED**

Run:

```bash
./tools/run-tests
```

Expected: `ModuleNotFoundError: No module named 'merge_config'`.

- [ ] **Step 3: Implement the merge API**

Create `tools/merge_config.py` with this public contract and behavior:

```python
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import tomlkit
from tomlkit.exceptions import TOMLKitError

KeyPath = tuple[str, ...]


@dataclass(frozen=True)
class MergeResult:
    text: str
    managed_paths: tuple[KeyPath, ...]


def _leaf_paths(value: Any, prefix: KeyPath = ()) -> tuple[KeyPath, ...]:
    if isinstance(value, Mapping):
        if not value:
            return ()
        paths: list[KeyPath] = []
        for key, child in value.items():
            paths.extend(_leaf_paths(child, prefix + (str(key),)))
        return tuple(paths)
    return (prefix,)


def _remove_path(document: Any, path: KeyPath) -> None:
    parents: list[tuple[Any, str]] = []
    node = document
    for key in path[:-1]:
        if not isinstance(node, Mapping) or key not in node:
            return
        parents.append((node, key))
        node = node[key]
    if isinstance(node, Mapping):
        node.pop(path[-1], None)
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, Mapping) and not child:
            parent.pop(key, None)
        else:
            break


def _merge_table(destination: Any, source: Mapping[str, Any]) -> None:
    for key, value in source.items():
        if isinstance(value, Mapping) and isinstance(destination.get(key), Mapping):
            _merge_table(destination[key], value)
        else:
            destination[key] = deepcopy(value)


def _parse(text: str, label: str):
    try:
        return tomlkit.parse(text or "")
    except TOMLKitError as error:
        raise ValueError(f"invalid {label} TOML: {error}") from error


def merge_config(
    live_text: str,
    overlay_text: str,
    previous_paths: Iterable[KeyPath],
) -> MergeResult:
    live = _parse(live_text, "live")
    overlay = _parse(overlay_text, "overlay")
    for path in sorted(tuple(previous_paths), key=len, reverse=True):
        if path:
            _remove_path(live, path)
    _merge_table(live, overlay)
    paths = tuple(sorted(_leaf_paths(overlay)))
    text = tomlkit.dumps(live)
    _parse(text, "merged")
    return MergeResult(text=text, managed_paths=paths)
```

- [ ] **Step 4: Run merge tests to verify GREEN**

Run:

```bash
./tools/run-tests
```

Expected: `Ran 7 tests ... OK`.

- [ ] **Step 5: Commit the merge engine**

```bash
git add tools/merge_config.py tests/test_merge_config.py
git commit -m "feat: merge owned Codex config keys"
```

## Task 3: Build manifest validation and read-only CLI commands

**Files:**
- Create: `tools/harness.py`
- Create: `bin/codex-harness`
- Create: `tests/test_harness.py`

- [ ] **Step 1: Write failing plan, status, inventory, and path-safety tests**

Create `tests/test_harness.py` with shared helpers and initial tests:

```python
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/codex-harness"


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.codex_home = self.home / ".codex"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "CODEX_HOME": str(self.codex_home),
            "CODEX_HELPER_HOST": "default",
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, check=True):
        return subprocess.run(
            [str(CLI), *args],
            cwd=ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            check=check,
        )

    def test_plan_is_read_only_and_lists_declared_assets(self):
        result = self.run_cli("plan", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual("0.1.0", payload["harness_version"])
        self.assertTrue(any(item["id"] == "global-agents" for item in payload["assets"]))
        self.assertFalse(self.codex_home.exists())

    def test_inventory_filters_by_kind(self):
        result = self.run_cli("list", "--kind", "agents", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual(3, len(payload["assets"]))
        self.assertTrue(all(item["category"] == "agents" for item in payload["assets"]))

    def test_status_reports_missing_without_mutating(self):
        result = self.run_cli("status", "--json", check=False)
        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertTrue(all(item["status"] == "missing" for item in payload["assets"]))

    def test_manifest_rejects_target_outside_approved_roots(self):
        bad = self.home / "bad.toml"
        text = (ROOT / "manifest.toml").read_text().replace(
            '${CODEX_HOME:-$HOME/.codex}/AGENTS.md',
            '/tmp/outside/AGENTS.md',
            1,
        )
        bad.write_text(text)
        result = self.run_cli("--manifest", str(bad), "plan", check=False)
        self.assertEqual(2, result.returncode)
        self.assertIn("outside approved roots", result.stderr)
```

- [ ] **Step 2: Run the CLI tests to verify RED**

Run:

```bash
./tools/run-tests
```

Expected: failures because `bin/codex-harness` does not exist.

- [ ] **Step 3: Implement immutable manifest and status types**

Create `tools/harness.py` with PEP 723 metadata and these public types:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.13.3"]
# ///
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from typing import Any, Mapping

from merge_config import merge_config

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_USAGE = 2
EXIT_CONFLICT = 3
EXIT_ROLLED_BACK = 4


@dataclass(frozen=True)
class Asset:
    id: str
    kind: str
    category: str
    source: Path
    target: Path
    scope: str
    version: str
    upstream: str | None
    license: str | None
    last_reviewed: str | None
    requires: tuple[str, ...]


@dataclass(frozen=True)
class Context:
    root: Path
    manifest_path: Path
    harness_version: str
    minimum_codex_version: str
    codex_home: Path
    user_skills: Path
    user_bin: Path
    config_base: Path
    host_overlay: Path
    local_overlay: Path | None
    state_path: Path
    backups_dir: Path
    assets: tuple[Asset, ...]


@dataclass(frozen=True)
class AssetStatus:
    id: str
    category: str
    version: str
    source: str
    target: str
    status: str
    actual_target: str | None
```

Implement the following functions with no global mutable state:

```python
_DEFAULT_VAR = re.compile(r"\$\{([A-Z_][A-Z0-9_]*):-([^}]+)\}")
_SIMPLE_VAR = re.compile(r"\$([A-Z_][A-Z0-9_]*)")


def expand_value(raw: str, env: Mapping[str, str]) -> str:
    def default_replace(match: re.Match[str]) -> str:
        name, fallback = match.groups()
        return env.get(name) or _SIMPLE_VAR.sub(lambda m: env.get(m.group(1), m.group(0)), fallback)
    value = _DEFAULT_VAR.sub(default_replace, raw)
    value = _SIMPLE_VAR.sub(lambda m: env.get(m.group(1), m.group(0)), value)
    if "$" in value:
        raise ValueError(f"unresolved variable in path: {raw}")
    return value


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_host(root: Path, host_dir: Path, explicit: str | None, env: Mapping[str, str]) -> tuple[Path, Path | None]:
    name = explicit or env.get("CODEX_HELPER_HOST") or os.uname().nodename.split(".")[0].lower()
    tracked = host_dir / f"{name}.toml"
    if not tracked.exists():
        tracked = host_dir / "default.toml"
    local = host_dir / f"{name}.local.toml"
    return tracked, local if local.exists() else None


def load_context(root: Path, manifest_path: Path, host: str | None, env: Mapping[str, str]) -> Context:
    data = tomllib.loads(manifest_path.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema_version")
    paths = data["paths"]
    codex_home = Path(expand_value(paths["codex_home"], env)).expanduser()
    user_skills = Path(expand_value(paths["user_skills"], env)).expanduser()
    user_bin = Path(expand_value(paths["user_bin"], env)).expanduser()
    approved = (codex_home, user_skills, user_bin)
    assets: list[Asset] = []
    ids: set[str] = set()
    targets: set[Path] = set()
    for item in data.get("assets", []):
        source = (root / item["source"]).resolve()
        target = Path(expand_value(item["target"], env)).expanduser()
        if not is_within(source, root) or not source.exists():
            raise ValueError(f"invalid source for {item['id']}")
        if not any(is_within(target, allowed) for allowed in approved):
            raise ValueError(f"target outside approved roots: {target}")
        if item["id"] in ids or target in targets:
            raise ValueError("duplicate asset id or target")
        ids.add(item["id"])
        targets.add(target)
        assets.append(Asset(
            id=item["id"],
            kind=item["kind"],
            category=item["category"],
            source=source,
            target=target,
            scope=item["scope"],
            version=item["version"],
            upstream=item.get("upstream"),
            license=item.get("license"),
            last_reviewed=item.get("last_reviewed"),
            requires=tuple(item.get("requires", [])),
        ))
    config = data["config"]
    host_dir = (root / config["host_dir"]).resolve()
    tracked, local = select_host(root, host_dir, host, env)
    return Context(
        root=root.resolve(),
        manifest_path=manifest_path.resolve(),
        harness_version=data["harness_version"],
        minimum_codex_version=data["minimum_codex_version"],
        codex_home=codex_home,
        user_skills=user_skills,
        user_bin=user_bin,
        config_base=(root / config["base"]).resolve(),
        host_overlay=tracked,
        local_overlay=local,
        state_path=Path(expand_value(config["state"], env)).expanduser(),
        backups_dir=Path(expand_value(config["backups"], env)).expanduser(),
        assets=tuple(assets),
    )


def inspect_asset(asset: Asset) -> AssetStatus:
    if not asset.target.exists() and not asset.target.is_symlink():
        status, actual = "missing", None
    elif not asset.target.is_symlink():
        status, actual = "conflict", None
    else:
        actual_path = Path(os.readlink(asset.target))
        if not actual_path.is_absolute():
            actual_path = asset.target.parent / actual_path
        actual = str(actual_path.resolve(strict=False))
        if actual_path.resolve(strict=False) == asset.source.resolve(strict=False) and asset.target.exists():
            status = "current"
        elif not asset.target.exists():
            status = "broken"
        else:
            status = "drifted"
    return AssetStatus(asset.id, asset.category, asset.version, str(asset.source), str(asset.target), status, actual)
```

- [ ] **Step 4: Implement read-only command routing**

Add `command_plan`, `command_status`, `command_inventory`, `command_list`, and `command_version`. All return dictionaries through a shared `emit(payload, json_mode)` function. `plan` must only call `inspect_asset` and this config preview helper; it must never call `mkdir`, `write_text`, `unlink`, `replace`, or `symlink_to`:

```python
def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"managed_paths": [], "assets": {}}
    return json.loads(path.read_text())


def combined_overlay(context: Context) -> str:
    documents = [context.config_base.read_text(), context.host_overlay.read_text()]
    if context.local_overlay:
        documents.append(context.local_overlay.read_text())
    result = ""
    for document in documents:
        result = merge_config(result, document, previous_paths=()).text
    return result


def preview_config(context: Context) -> dict[str, Any]:
    live_path = context.codex_home / "config.toml"
    live_text = live_path.read_text() if live_path.exists() else ""
    state = read_state(context.state_path) if context.state_path.exists() else {"managed_paths": []}
    previous = tuple(tuple(path) for path in state.get("managed_paths", []))
    result = merge_config(live_text, combined_overlay(context), previous)
    return {
        "target": str(live_path),
        "status": "current" if result.text == live_text else "drifted",
        "managed_paths": [list(path) for path in result.managed_paths],
        "changes": result.text != live_text,
    }
```

Task 4 reuses these side-effect-free helpers and adds writes and backups without renaming them. `command_plan` sets top-level `changes` to the list of non-current asset IDs plus `config` when `preview_config()["changes"]` is true. `command_status` includes config status and exits 1 when either a link or config is non-current.

Serialize inventory and version metadata with Paths converted to strings:

```python
def asset_record(asset: Asset, status: AssetStatus | None = None) -> dict[str, Any]:
    record = {
        "id": asset.id,
        "kind": asset.kind,
        "category": asset.category,
        "source": str(asset.source),
        "target": str(asset.target),
        "scope": asset.scope,
        "version": asset.version,
        "upstream": asset.upstream,
        "license": asset.license,
        "last_reviewed": asset.last_reviewed,
        "requires": list(asset.requires),
    }
    if status:
        record["status"] = status.status
        record["actual_target"] = status.actual_target
    return record
```

Use this parser shape so later tasks add mutating commands without renaming arguments:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-harness")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--host")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "status", "inventory"):
        child = sub.add_parser(name)
        child.add_argument("--json", action="store_true")
    list_parser = sub.add_parser("list")
    list_parser.add_argument("--kind", choices=("skills", "agents", "profiles", "rules", "utilities"), required=True)
    list_parser.add_argument("--json", action="store_true")
    version = sub.add_parser("version")
    version.add_argument("asset_id", nargs="?")
    version.add_argument("--json", action="store_true")
    return parser
```

Map category aliases exactly: `skills -> skills`, `agents -> agents`, `profiles -> profiles`, `rules -> rules`, `utilities -> utilities`. `status` exits 1 when any asset is not `current`; `plan` exits 0 unless manifest validation fails; invalid manifest exits 2 with a concise stderr message.

- [ ] **Step 5: Create the stable launcher**

Create executable `bin/codex-harness`:

```sh
#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec uv run --with tomlkit==0.13.3 python "$ROOT/tools/harness.py" "$@"
```

- [ ] **Step 6: Run tests and verify GREEN**

Run:

```bash
chmod +x bin/codex-harness
./tools/run-tests
```

Expected: `Ran 11 tests ... OK`.

- [ ] **Step 7: Commit the read-only CLI**

```bash
git add tools/harness.py bin/codex-harness tests/test_harness.py
git commit -m "feat: add Codex harness planning and status"
```

## Task 4: Add transactional apply, snapshot, restore, and unlink

**Files:**
- Modify: `tools/harness.py`
- Modify: `tests/test_harness.py`

- [ ] **Step 1: Add failing transaction tests**

Append tests that prove idempotency, preservation, rollback, restore, and unlink:

```python
    def test_apply_is_idempotent_and_preserves_unmanaged_entries(self):
        self.codex_home.mkdir(parents=True)
        live = self.codex_home / "config.toml"
        live.write_text('[plugins.demo]\nenabled = true\n')
        external = self.home / ".agents/skills/external"
        external.mkdir(parents=True)
        (external / "SKILL.md").write_text("external")
        self.run_cli("apply", "--yes")
        first = live.read_bytes()
        self.run_cli("apply", "--yes")
        self.assertEqual(first, live.read_bytes())
        self.assertTrue((external / "SKILL.md").exists())
        self.assertEqual((ROOT / "AGENTS.md").resolve(), (self.codex_home / "AGENTS.md").resolve())
        plan = json.loads(self.run_cli("plan", "--json").stdout)
        self.assertFalse(plan["changes"])

    def test_apply_rolls_back_after_injected_failure(self):
        self.codex_home.mkdir(parents=True)
        live = self.codex_home / "config.toml"
        live.write_text('model = "before"\n')
        env = {**self.env, "CODEX_HELPER_FAIL_AFTER": "1"}
        result = subprocess.run(
            [str(CLI), "apply", "--yes"], cwd=ROOT, env=env, text=True, capture_output=True
        )
        self.assertEqual(4, result.returncode)
        self.assertEqual('model = "before"\n', live.read_text())
        self.assertFalse((self.codex_home / "AGENTS.md").exists())

    def test_snapshot_restore_and_unlink_touch_only_managed_state(self):
        self.run_cli("apply", "--yes")
        snapshot = json.loads(self.run_cli("snapshot", "--json").stdout)["snapshot_id"]
        agents_link = self.codex_home / "AGENTS.md"
        agents_link.unlink()
        self.run_cli("restore", snapshot, "--yes")
        self.assertTrue(agents_link.is_symlink())
        self.run_cli("unlink", "--yes")
        self.assertFalse(agents_link.exists())
        self.assertTrue((self.codex_home / "config.toml").exists())

    def test_apply_removes_only_a_stale_previously_owned_link(self):
        stale_source = ROOT / "AGENTS.md"
        stale_target = self.codex_home / "agents/retired.toml"
        stale_target.parent.mkdir(parents=True)
        stale_target.symlink_to(stale_source)
        state = self.codex_home / ".codex-helper/state.json"
        state.parent.mkdir(parents=True)
        state.write_text(json.dumps({
            "managed_paths": [],
            "assets": {
                "retired-agent": {
                    "source": str(stale_source),
                    "target": str(stale_target),
                    "kind": "symlink",
                    "category": "agents",
                    "version": "0.9.0"
                }
            }
        }))
        self.run_cli("apply", "--yes")
        self.assertFalse(stale_target.exists())
```

- [ ] **Step 2: Run tests to verify RED**

Run `./tools/run-tests`.

Expected: argparse rejects `apply`, `snapshot`, `restore`, and `unlink`.

- [ ] **Step 3: Implement state and backup receipts**

Keep the Task 3 `read_state` helper unchanged and add immutable backup/write helpers to `tools/harness.py`:

```python
from datetime import datetime, timezone
import shutil
import tempfile


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def new_snapshot_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_target(target: Path, snapshot_dir: Path) -> dict[str, Any]:
    entry = {"target": str(target), "type": "missing"}
    if target.is_symlink():
        entry.update(type="symlink", link=os.readlink(target))
    elif target.is_file():
        relative = Path("files") / hashlib.sha256(str(target).encode()).hexdigest()
        destination = snapshot_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
        entry.update(type="file", backup=str(relative), sha256=sha256(target))
    elif target.is_dir():
        relative = Path("dirs") / hashlib.sha256(str(target).encode()).hexdigest()
        shutil.copytree(target, snapshot_dir / relative, symlinks=True)
        entry.update(type="directory", backup=str(relative))
    return entry
```

Snapshots include `receipt.json` with `snapshot_id`, `harness_version`, `git_revision`, `host_overlay`, ordered `entries`, live config, and prior state. Never include auth, sessions, logs, caches, plugin directories, or undeclared skills.

- [ ] **Step 4: Implement transactional link and config application**

Keep the Task 3 `combined_overlay` helper unchanged and add these write helpers:

```python
def atomic_symlink(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.codex-helper-tmp"
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    temporary.symlink_to(source)
    os.replace(temporary, target)


def apply_config(context: Context, previous_state: Mapping[str, Any]) -> tuple[str, tuple[tuple[str, ...], ...]]:
    live_path = context.codex_home / "config.toml"
    live_text = live_path.read_text() if live_path.exists() else ""
    previous = tuple(tuple(path) for path in previous_state.get("managed_paths", []))
    result = merge_config(live_text, combined_overlay(context), previous)
    atomic_write(live_path, result.text.encode(), mode=0o600)
    return result.text, result.managed_paths
```

`command_apply` must:

1. Build the complete asset/config plan and return success without a snapshot when it contains no changes.
2. Include stale entries from prior `state["assets"]`; remove one only when its live target is still a symlink to the recorded source, otherwise report a conflict and preserve it.
3. Refuse conflicts unless `--yes` was supplied after plan output.
4. Create one snapshot before the first replacement.
5. Apply assets in manifest order with atomic symlink replacement.
6. Apply config and then atomically write state with this exact shape:

```python
def build_state(context: Context, managed_paths: tuple[tuple[str, ...], ...]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "harness_version": context.harness_version,
        "host_overlay": str(context.host_overlay),
        "managed_paths": [list(path) for path in managed_paths],
        "assets": {
            asset.id: {
                "source": str(asset.source),
                "target": str(asset.target),
                "kind": asset.kind,
                "category": asset.category,
                "version": asset.version,
            }
            for asset in context.assets
        },
    }
```

7. Honor `CODEX_HELPER_FAIL_AFTER` only in tests by raising after N completed mutations.
8. On any exception, restore receipt entries in reverse order and exit 4.

`command_unlink` creates a snapshot, iterates the union of current manifest assets and prior state assets, removes only links whose current target matches the recorded source, removes prior managed config paths through `merge_config(live, "", previous_paths)`, and deletes harness state. It preserves conflicting or externally changed targets and exits 3.

- [ ] **Step 5: Add parser entries for mutating commands**

```python
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--yes", action="store_true")
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--json", action="store_true")
    restore = sub.add_parser("restore")
    restore.add_argument("snapshot_id")
    restore.add_argument("--yes", action="store_true")
    unlink = sub.add_parser("unlink")
    unlink.add_argument("--yes", action="store_true")
```

- [ ] **Step 6: Run transaction tests to verify GREEN**

Run `./tools/run-tests`.

Expected: all tests pass and no test path escapes the temporary home.

- [ ] **Step 7: Commit transactional operations**

```bash
git add tools/harness.py tests/test_harness.py
git commit -m "feat: apply and restore Codex harness state"
```

## Task 5: Add cross-machine bootstrap and operational entry points

**Files:**
- Create: `install.sh`
- Create: `bin/codex-external-review`
- Modify: `manifest.toml`
- Modify: `tools/harness.py`
- Modify: `tests/test_harness.py`

- [ ] **Step 1: Add failing bootstrap, host-init, and utility tests**

```python
    def test_bootstrap_creates_only_parent_directories(self):
        self.run_cli("bootstrap")
        self.assertTrue(self.codex_home.is_dir())
        self.assertTrue((self.home / ".agents/skills").is_dir())
        self.assertTrue((self.home / ".local/bin").is_dir())
        self.assertFalse((self.codex_home / "AGENTS.md").exists())

    def test_host_init_creates_non_secret_skeleton(self):
        checkout = self.home / "checkout"
        subprocess.run(["cp", "-R", str(ROOT), str(checkout)], check=True)
        cli = checkout / "bin/codex-harness"
        subprocess.run([str(cli), "host", "init", "gems"], cwd=checkout, env=self.env, check=True)
        text = (checkout / "sources/config/hosts/gems.toml").read_text()
        self.assertIn("Host-specific non-secret", text)
        self.assertNotRegex(text.lower(), r"token|password|bearer")

    def test_utilities_are_manifest_managed(self):
        self.run_cli("apply", "--yes")
        self.assertEqual(ROOT / "bin/codex-harness", (self.home / ".local/bin/codex-harness").resolve())
        self.assertEqual(ROOT / "bin/codex-external-review", (self.home / ".local/bin/codex-external-review").resolve())
```

- [ ] **Step 2: Run tests to verify RED**

Run `./tools/run-tests`.

Expected: missing bootstrap/host commands and utility manifest entries.

- [ ] **Step 3: Add utility assets to `manifest.toml`**

Append:

```toml
[[assets]]
id = "utility-codex-harness"
kind = "utility"
category = "utilities"
source = "bin/codex-harness"
target = "$HOME/.local/bin/codex-harness"
scope = "global"
version = "1.0.0"

[[assets]]
id = "utility-external-review"
kind = "utility"
category = "utilities"
source = "bin/codex-external-review"
target = "$HOME/.local/bin/codex-external-review"
scope = "global"
version = "1.0.0"
```

- [ ] **Step 4: Implement bootstrap and host init**

`bootstrap` creates only `codex_home`, `user_skills`, `user_bin`, `codex_home/agents`, and `codex_home/rules`. It prints PATH/restart instructions and never links or merges.

`host init NAME` accepts only `[a-z0-9][a-z0-9_-]*`, refuses an existing file, and writes exactly:

```toml
# Host-specific non-secret Codex settings for NAME.
# Keep secrets in environment variables or Codex credential storage.
```

Replace `NAME` with the validated host name. Add parser nesting:

```python
    sub.add_parser("bootstrap")
    host_parser = sub.add_parser("host")
    host_sub = host_parser.add_subparsers(dest="host_command", required=True)
    host_init = host_sub.add_parser("init")
    host_init.add_argument("name")
```

- [ ] **Step 5: Create the external-review alias and first-run installer**

Create executable `bin/codex-external-review`:

```sh
#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
exec "$ROOT/bin/codex-harness" external-review "$@"
```

Create executable `install.sh`:

```sh
#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

command -v uv >/dev/null 2>&1 || {
  echo "ERROR: uv is required: https://docs.astral.sh/uv/" >&2
  exit 2
}
command -v codex >/dev/null 2>&1 || {
  echo "ERROR: codex CLI is required" >&2
  exit 2
}

"$ROOT/bin/codex-harness" "$@" bootstrap
"$ROOT/bin/codex-harness" "$@" plan
printf "Apply the planned Codex harness changes? [y/N] "
read -r answer
case "$answer" in
  y|Y|yes|YES) "$ROOT/bin/codex-harness" "$@" apply --yes ;;
  *) echo "No changes applied."; exit 0 ;;
esac
"$ROOT/bin/codex-harness" "$@" doctor
```

The implementation must normalize global `--host NAME` before subcommands so `./install.sh --host rock` works for all delegated calls.

- [ ] **Step 6: Run tests and installer dry run**

Run:

```bash
chmod +x install.sh bin/codex-external-review
./tools/run-tests
tmp_home=$(mktemp -d)
env HOME="$tmp_home" CODEX_HOME="$tmp_home/.codex" sh -c "printf 'n\\n' | ./install.sh --host default"
```

Expected: tests pass; installer prints a plan and `No changes applied.`. The temporary home contains parent directories but no managed links.

- [ ] **Step 7: Commit bootstrap and utilities**

```bash
git add install.sh bin manifest.toml tools/harness.py tests/test_harness.py
git commit -m "feat: add cross-machine Codex bootstrap"
```

## Task 6: Install the native parallel-review workflow

**Required execution skill:** Read and follow `writing-skills` before authoring or validating the skill.

**Files:**
- Create: `sources/skills/parallel-review/SKILL.md`
- Create: `sources/skills/parallel-review/agents/openai.yaml`
- Modify: `manifest.toml`
- Modify: `tests/test_sources.py`

- [ ] **Step 1: Add the failing skill contract**

```python
    def test_parallel_review_skill_contract(self):
        skill = ROOT / "sources/skills/parallel-review/SKILL.md"
        text = skill.read_text()
        self.assertIn("name: parallel-review", text)
        self.assertIn("scanner", text)
        self.assertIn("reviewer", text)
        self.assertIn("verifier", text)
        self.assertIn("Wait for all", text)
        self.assertIn("root agent", text)
        self.assertIn("Do not delegate concurrent writes", text)
```

Also extend the manifest-source test so every `source` exists.

- [ ] **Step 2: Run tests to verify RED**

Run `./tools/run-tests`.

Expected: missing `sources/skills/parallel-review/SKILL.md`.

- [ ] **Step 3: Create the focused skill**

Create `sources/skills/parallel-review/SKILL.md`:

```markdown
---
name: parallel-review
description: Use when the user explicitly requests parallel review, multiple independent review perspectives, or one agent per review concern. Do not use for simple single-file review or concurrent write-heavy implementation.
---

# Parallel Review

1. Restate the review target, comparison base, constraints, and required output.
2. Split only independent read-heavy concerns. Default roles:
   - `scanner`: affected paths and factual repository map.
   - `reviewer`: correctness, security, regression, and maintainability findings.
   - `verifier`: acceptance criteria, test gaps, and fresh evidence.
3. Spawn only the roles needed. Give each a bounded prompt, read-only scope, and expected evidence format.
4. Wait for all requested agents before synthesizing.
5. The root agent independently checks file references and resolves contradictions.
6. Return one deduplicated report ordered by severity, followed by test gaps and unresolved questions.

## Boundaries

- Do not delegate concurrent writes to the same checkout.
- Subagents do not commit, push, approve, or make the final verdict.
- The root agent owns scope, mutations, consolidation, and final judgment.
- If work must be written in parallel, first isolate it in separate Git worktrees and obtain user authorization for that expanded workflow.
```

Create `sources/skills/parallel-review/agents/openai.yaml`:

```yaml
interface:
  display_name: "Parallel Review"
  short_description: "Run bounded read-only review perspectives in parallel"
  default_prompt: "Review this change with independent scanner, reviewer, and verifier perspectives, then consolidate the evidence."
```

- [ ] **Step 4: Add the skill asset**

Append to `manifest.toml`:

```toml
[[assets]]
id = "skill-parallel-review"
kind = "symlink"
category = "skills"
source = "sources/skills/parallel-review"
target = "$HOME/.agents/skills/parallel-review"
scope = "global"
version = "1.0.0"
upstream = "https://learn.chatgpt.com/docs/agent-configuration/subagents"
license = "local-adaptation"
last_reviewed = "2026-07-19"
```

- [ ] **Step 5: Run tests and a metadata smoke check**

Run:

```bash
./tools/run-tests
./bin/codex-harness list --kind skills --json
```

Expected: tests pass and JSON lists `skill-parallel-review` once.

- [ ] **Step 6: Commit the parallel-review workflow**

```bash
git add manifest.toml sources/skills/parallel-review tests/test_sources.py
git commit -m "feat: add native parallel review skill"
```

## Task 7: Install bounded dual-loop external review

**Required execution skill:** Read and follow `writing-skills` before authoring or validating the skill.

**Files:**
- Create: `sources/skills/dual-loop-review/SKILL.md`
- Create: `sources/skills/dual-loop-review/agents/openai.yaml`
- Create: `sources/skills/dual-loop-review/references/reviewer-prompt.md`
- Create: `sources/skills/dual-loop-review/schemas/verdict.schema.json`
- Modify: `manifest.toml`
- Modify: `tools/harness.py`
- Create: `tests/test_external_review.py`

- [ ] **Step 1: Write failing external-review tests**

Create `tests/test_external_review.py`:

```python
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/codex-external-review"


class ExternalReviewTests(unittest.TestCase):
    def test_external_review_is_ephemeral_read_only_and_structured(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            log = root / "args.json"
            stub = root / "codex"
            stub.write_text(
                "#!/bin/sh\n"
                "python3 - \"$@\" <<'PY'\n"
                "import json, pathlib, sys\n"
                f"pathlib.Path({str(log)!r}).write_text(json.dumps(sys.argv[1:]))\n"
                "args = sys.argv[1:]\n"
                "out = args[args.index('--output-last-message') + 1]\n"
                "pathlib.Path(out).write_text(json.dumps({'verdict':'pass','summary':'ok','findings':[],'requested_evidence':[]}))\n"
                "PY\n"
            )
            stub.chmod(0o755)
            env = {**os.environ, "PATH": f"{root}:{os.environ['PATH']}"}
            result = subprocess.run(
                [str(CLI), "--repo", str(repo), "--cycle", "1"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual("pass", json.loads(result.stdout)["verdict"])
            args = json.loads(log.read_text())
            self.assertIn("--ephemeral", args)
            self.assertEqual("read-only", args[args.index("--sandbox") + 1])
            self.assertIn("--output-schema", args)

    def test_cycle_must_be_between_one_and_three(self):
        result = subprocess.run(
            [str(CLI), "--repo", str(ROOT), "--cycle", "4"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("cycle must be between 1 and 3", result.stderr)
```

- [ ] **Step 2: Run tests to verify RED**

Run `./tools/run-tests`.

Expected: `external-review` is not recognized.

- [ ] **Step 3: Create the verdict schema and reviewer prompt**

Create `sources/skills/dual-loop-review/schemas/verdict.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["verdict", "summary", "findings", "requested_evidence"],
  "properties": {
    "verdict": {"enum": ["pass", "changes_requested", "blocked"]},
    "summary": {"type": "string", "minLength": 1},
    "findings": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["severity", "title", "evidence", "file"],
        "properties": {
          "severity": {"enum": ["high", "medium", "low"]},
          "title": {"type": "string"},
          "evidence": {"type": "string"},
          "file": {"type": ["string", "null"]}
        }
      }
    },
    "requested_evidence": {"type": "array", "items": {"type": "string"}}
  }
}
```

Create `references/reviewer-prompt.md`:

```markdown
Review the current repository diff as an independent, read-only owner.

Check the stated acceptance criteria, correctness, security, regressions, maintainability, and the supplied verification evidence. Inspect files and run only read-only diagnostics. Do not edit, commit, push, or approve external actions.

Return `pass` only when there are no actionable findings and the supplied evidence is sufficient. Return `changes_requested` for fixable findings. Return `blocked` when missing authority, environment, or evidence prevents a reliable verdict.
```

- [ ] **Step 4: Implement one external review invocation**

Add parser arguments:

```python
    external = sub.add_parser("external-review")
    external.add_argument("--repo", type=Path, required=True)
    external.add_argument("--cycle", type=int, default=1)
    external.add_argument("--evidence", type=Path)
```

Implement:

```python
def command_external_review(context: Context, repo: Path, cycle: int, evidence: Path | None) -> int:
    if cycle < 1 or cycle > 3:
        print("ERROR: cycle must be between 1 and 3", file=sys.stderr)
        return EXIT_USAGE
    if not (repo / ".git").exists():
        print("ERROR: --repo must be a Git repository", file=sys.stderr)
        return EXIT_USAGE
    skill = context.root / "sources/skills/dual-loop-review"
    prompt = (skill / "references/reviewer-prompt.md").read_text()
    if evidence:
        prompt += "\n\nVerification evidence:\n" + evidence.read_text()
    schema = skill / "schemas/verdict.schema.json"
    with tempfile.TemporaryDirectory(prefix="codex-external-review-") as temp:
        output = Path(temp) / "verdict.json"
        command = [
            "codex", "exec", "--ephemeral", "--sandbox", "read-only",
            "--profile", "deep-review", "--cd", str(repo.resolve()),
            "--output-schema", str(schema), "--output-last-message", str(output), "-",
        ]
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True)
        if completed.returncode != 0:
            print(completed.stderr, file=sys.stderr, end="")
            return EXIT_DRIFT
        payload = json.loads(output.read_text())
        allowed = {"pass", "changes_requested", "blocked"}
        if payload.get("verdict") not in allowed:
            print("ERROR: invalid external review verdict", file=sys.stderr)
            return EXIT_DRIFT
        print(json.dumps(payload, indent=2, sort_keys=True))
        return EXIT_OK
```

- [ ] **Step 5: Create the dual-loop skill and metadata**

Create `sources/skills/dual-loop-review/SKILL.md`:

```markdown
---
name: dual-loop-review
description: Use after a non-trivial implementation when the user requests independent review, fresh-context verification, or an internal/external review loop. Do not use for read-only questions or before the implementation has fresh local evidence.
---

# Dual-Loop Review

## Internal loop

1. Restate measurable acceptance criteria.
2. Make the smallest scoped change.
3. Run the relevant tests, build, or behavior check.
4. Read failures, correct the implementation, and rerun fresh checks.
5. Save a concise evidence file containing commands, exit codes, and remaining limitations.

## External loop

1. From the target repository, save evidence at `.codex-loop/evidence.md` and run `codex-external-review --repo "$PWD" --cycle 1 --evidence .codex-loop/evidence.md`.
2. On `pass`, independently confirm the final diff and report completion.
3. On `changes_requested`, validate each finding, apply only correct fixes in the active agent, rerun internal evidence, then run cycle 2.
4. Use cycle 3 only when cycle 2 found a distinct actionable issue. Never exceed three cycles.
5. On `blocked`, repeated findings, exhausted cycles, or missing authority, stop and report the exact blocker.

## Boundaries

- The external reviewer is ephemeral and read-only.
- Do not use bypass-sandbox flags.
- Do not turn uncertainty or an unavailable test into `pass`.
- Propose persistent `AGENTS.md`, rule, or skill changes separately; require user authorization before changing global policy.
```

Create `agents/openai.yaml`:

```yaml
interface:
  display_name: "Dual-Loop Review"
  short_description: "Verify internally, then review in a fresh read-only Codex context"
  default_prompt: "Run the bounded internal/external review loop for this implementation."
```

- [ ] **Step 6: Add the skill asset to the manifest**

```toml
[[assets]]
id = "skill-dual-loop-review"
kind = "symlink"
category = "skills"
source = "sources/skills/dual-loop-review"
target = "$HOME/.agents/skills/dual-loop-review"
scope = "global"
version = "1.0.0"
upstream = "https://www.philschmid.de/inner-loop-vs-outer-loop"
license = "local-adaptation"
last_reviewed = "2026-07-19"
```

- [ ] **Step 7: Run tests to verify GREEN**

Run `./tools/run-tests`.

Expected: all source, merge, harness, and external review tests pass without a real model call.

- [ ] **Step 8: Commit the dual-loop workflow**

```bash
git add manifest.toml sources/skills/dual-loop-review tools/harness.py tests/test_external_review.py
git commit -m "feat: add bounded external review loop"
```

## Task 8: Complete doctor, secret scanning, and JSON contracts

**Files:**
- Modify: `tools/harness.py`
- Modify: `tests/test_harness.py`
- Modify: `tests/test_sources.py`

- [ ] **Step 1: Write failing doctor and redaction tests**

```python
    def test_doctor_passes_for_sources_and_applied_temp_home(self):
        self.run_cli("apply", "--yes")
        result = self.run_cli("doctor", "--json")
        payload = json.loads(result.stdout)
        self.assertEqual("healthy", payload["health"])
        self.assertTrue(all(check["status"] == "pass" for check in payload["checks"]))

    def test_doctor_detects_secret_in_managed_source_without_printing_value(self):
        checkout = self.home / "secret-checkout"
        subprocess.run(["cp", "-R", str(ROOT), str(checkout)], check=True)
        bad = checkout / "sources/config/hosts/default.local.toml"
        bad.write_text('api_token = "super-secret-value"\n')
        result = subprocess.run(
            [str(checkout / "bin/codex-harness"), "doctor", "--json"],
            cwd=checkout,
            env=self.env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("suspected secret", result.stdout)
        self.assertNotIn("super-secret-value", result.stdout)

    def test_operational_sources_have_no_sibling_harness_path(self):
        self.run_cli("apply", "--yes")
        result = self.run_cli("doctor", "--json")
        payload = json.loads(result.stdout)
        boundary = next(check for check in payload["checks"] if check["id"] == "self-contained")
        self.assertEqual("pass", boundary["status"])
```

- [ ] **Step 2: Run tests to verify RED**

Run `./tools/run-tests`.

Expected: `doctor` is not recognized.

- [ ] **Step 3: Implement doctor checks**

Add `doctor --json` and return a list of `{id, status, message}` without raw config values. Checks:

1. `manifest`: schema, unique IDs/targets, source existence, approved roots.
2. `toml`: base, selected host, local host, profiles, and agents parse.
3. `guidance`: required five headings exist.
4. `skills`: every skill source has `SKILL.md` with name/description and every directly referenced local file exists.
5. `agents`: required fields exist and `sandbox_mode == "read-only"`.
6. `links`: every applied managed link resolves to its declared source.
7. `config`: live TOML parses and state-owned key paths equal the effective overlay paths.
8. `secrets`: parse TOML/JSON/YAML structured keys and scan shell/Python assignments for key names matching `token|secret|password|credential|auth[_-]?key|api[_-]?key`; allow environment-variable references, ignore prose-only Markdown mentions, and never print matched values.
9. `self-contained`: resolve each managed source under `context.root`; scan only operational sources (`AGENTS.md`, `manifest.toml`, `bin/`, `tools/`, `sources/`) for an absolute path containing `/claude-harness-helper`.
10. `codex-version`: parse `codex --version` and compare numeric components to `minimum_codex_version`.

Do not inspect the sibling repository to implement the self-contained check.

- [ ] **Step 4: Validate rules with Codex execpolicy**

When `codex execpolicy check` is available, doctor runs:

```bash
codex execpolicy check --pretty --rules sources/rules/codex-helper.rules codex-harness status
```

Expected decision: allow. If the installed CLI lacks `execpolicy`, doctor reports a warning without failing unrelated checks.

- [ ] **Step 5: Run complete tests**

Run:

```bash
./tools/run-tests
git diff --check
```

Expected: all tests pass; `git diff --check` exits 0.

- [ ] **Step 6: Commit doctor and contracts**

```bash
git add tools/harness.py tests/test_harness.py tests/test_sources.py
git commit -m "feat: validate Codex harness health"
```

## Task 9: Write operator and cross-machine documentation

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/operations.md`
- Create: `docs/cross-machine-bootstrap.md`
- Create: `docs/sources.md`
- Modify: `tests/test_sources.py`

- [ ] **Step 1: Write failing documentation-link tests**

```python
    def test_operator_docs_exist_and_readme_links_them(self):
        readme = (ROOT / "README.md").read_text()
        for relative in (
            "docs/architecture.md",
            "docs/operations.md",
            "docs/cross-machine-bootstrap.md",
            "docs/sources.md",
        ):
            self.assertTrue((ROOT / relative).is_file())
            self.assertIn(relative, readme)

    def test_docs_define_safe_update_sequence(self):
        text = (ROOT / "docs/operations.md").read_text()
        sequence = ["git pull --ff-only", "codex-harness plan", "codex-harness apply", "codex-harness doctor"]
        positions = [text.index(item) for item in sequence]
        self.assertEqual(positions, sorted(positions))
```

- [ ] **Step 2: Run tests to verify RED**

Run `./tools/run-tests`.

Expected: missing `README.md` and operator docs.

- [ ] **Step 3: Write focused documentation**

`README.md` must contain:

- one-sentence purpose
- prerequisites: Git, `uv`, Codex CLI 0.144.5+
- first-run `./install.sh --host rock`
- command table matching Task 5/8 parser names
- explicit runtime-owned exclusions
- links to all four docs
- note that follow-up external-agent and SDD/TDD research is deferred until real-machine AC completion

`docs/architecture.md` must explain manifest ownership, individual links, live-config merge, state JSON, backup receipt, runtime exclusions, and the permanent independence boundary.

`docs/operations.md` must document exact daily commands, JSON output, drift exit codes, snapshot/restore/unlink confirmation, and this update sequence:

```bash
git pull --ff-only
codex-harness plan
codex-harness apply
codex-harness doctor
```

`docs/cross-machine-bootstrap.md` must document clone, `host init`, tracked versus `.local.toml` overlays, PATH, restart, and rollback.

`docs/sources.md` must attribute the four OpenAI pages, Phil Schmid's loop article, and Ralph. State that both installed skills are local adaptations and no third-party code was vendored.

- [ ] **Step 4: Run documentation tests and doctor**

Run:

```bash
./tools/run-tests
./bin/codex-harness doctor --json
```

Expected: tests pass. Doctor may report live-link drift before real apply, but source, manifest, TOML, skill, agent, secret, and self-contained checks pass.

- [ ] **Step 5: Commit documentation**

```bash
git add README.md docs/architecture.md docs/operations.md docs/cross-machine-bootstrap.md docs/sources.md tests/test_sources.py
git commit -m "docs: explain Codex harness operations"
```

## Task 10: Verify, apply to the real Codex home, and close the migration boundary

**Files:**
- Modify only if verification finds a requirement-traceable defect: files created in Tasks 1-9
- Runtime targets after approval: `~/.codex/AGENTS.md`, `~/.codex/config.toml`, declared `~/.codex/agents/*`, profiles, rule, `$HOME/.agents/skills/*`, and `$HOME/.local/bin/*`

- [ ] **Step 1: Run the complete isolated suite twice**

Run:

```bash
./tools/run-tests
./tools/run-tests
```

Expected: both runs exit 0 with the same test count.

- [ ] **Step 2: Run isolated bootstrap and idempotency verification**

Run:

```bash
temp_home=$(mktemp -d)
HOME="$temp_home" CODEX_HOME="$temp_home/.codex" CODEX_HELPER_HOST=default ./bin/codex-harness bootstrap
HOME="$temp_home" CODEX_HOME="$temp_home/.codex" CODEX_HELPER_HOST=default ./bin/codex-harness apply --yes
HOME="$temp_home" CODEX_HOME="$temp_home/.codex" CODEX_HELPER_HOST=default ./bin/codex-harness doctor --json
HOME="$temp_home" CODEX_HOME="$temp_home/.codex" CODEX_HELPER_HOST=default ./bin/codex-harness plan --json
```

Expected: doctor health is `healthy`; final plan contains `"changes": []`.

- [ ] **Step 3: Run static final checks**

Run:

```bash
git diff --check
rg -n '/[^ ]*/claude-harness-helper' AGENTS.md manifest.toml bin tools sources
git status --short
```

Expected: diff check exits 0; `rg` returns no matches; Git shows only intentional implementation changes, or is clean after task commits.

- [ ] **Step 4: Preview the real-home migration**

Run:

```bash
./bin/codex-harness --host rock plan
./bin/codex-harness --host rock inventory
```

Expected: output lists only manifest-declared links plus owned config keys. It must not propose changes to auth, sessions, caches, plugins, marketplaces, projects, desktop state, `rules/default.rules`, or undeclared skills.

- [ ] **Step 5: Obtain filesystem approval and snapshot the real home**

Because this writes outside the repository, request explicit tool approval for:

```bash
./bin/codex-harness --host rock snapshot --json
```

Expected: exit 0 and a timestamped snapshot receipt under `~/.codex/backups/codex-helper/`.

- [ ] **Step 6: Apply the real-home migration**

After reviewing Step 4 and the snapshot ID, request approval and run:

```bash
./bin/codex-harness --host rock apply --yes
```

Expected: exit 0. Existing conflicting global guidance link is backed up, not followed or read.

- [ ] **Step 7: Run fresh real-home evidence**

Run:

```bash
codex-harness --host rock status --json
codex-harness --host rock inventory --json
codex-harness --host rock doctor --json
codex-harness --host rock plan --json
readlink ~/.codex/AGENTS.md
```

Expected:

- status exit 0 with every managed asset `current`
- doctor `health: healthy`
- plan `changes: []`
- `readlink` points to `/Users/denny/Project/codex-helper/AGENTS.md`
- config remains a real file, not a symlink

- [ ] **Step 8: Run optional live workflow smoke tests with user approval**

Ask before consuming model usage. If approved, use a harmless temporary Git fixture:

```bash
fixture=$(mktemp -d)
git -C "$fixture" init -q
printf 'hello\n' > "$fixture/example.txt"
git -C "$fixture" add example.txt
git -C "$fixture" -c user.name='Codex Harness Test' -c user.email='codex-harness@example.invalid' commit -qm init
printf 'hello world\n' > "$fixture/example.txt"
codex-external-review --repo "$fixture" --cycle 1
```

Expected: valid JSON matching `verdict.schema.json`; the fixture diff remains unchanged by the reviewer.

For native parallel review, start a new Codex task and explicitly invoke `$parallel-review` on the harmless fixture. Verify scanner/reviewer/verifier are read-only and the root returns a consolidated report.

- [ ] **Step 9: Run requirements traceability check**

Record an evidence table in the final handoff mapping AC-01 through AC-11 to the exact commands and outputs from Steps 1-8. Any `not run` or `blocked` entry prevents a blanket completion claim.

- [ ] **Step 10: Commit any verification-only fixes**

If verification required no source change, do not create an empty commit. If it found a scoped defect, rerun all affected checks and commit only the fix:

```bash
git add AGENTS.md manifest.toml install.sh bin tools sources tests README.md docs/architecture.md docs/operations.md docs/cross-machine-bootstrap.md docs/sources.md
git commit -m "fix: correct Codex harness verification defect"
```

Expected: worktree clean and all fresh checks pass.

## Task 11: Begin ordered follow-up research only after harness completion

**Files:**
- Create: `docs/research/codex-external-review-agents-2026-07.md`
- Create: `docs/research/sdd-tdd-skills-2026-07.md`

- [ ] **Step 1: Gate the follow-up**

Confirm the Task 10 evidence table has `pass` for AC-01 through AC-11. If any criterion is not passed, return to its owning task and do not start research.

- [ ] **Step 2: Research external review-only agents**

Use current official Codex documentation first, then primary community sources. Compare process isolation, model independence, read-only guarantees, context freshness, structured verdicts, cost, and integration with Codex. Do not consult the sibling Claude harness repository.

- [ ] **Step 3: Research SDD/TDD skills**

After the external-agent report is complete, invoke `find-skills` to discover candidates and evaluate each candidate's trigger precision, repository activity, license, Codex compatibility, test discipline, and overlap with the installed workflows. Recommend before installing; do not install third-party code without a separate user decision.

---

## Final verification checklist

- [ ] AC-01 cross-machine bootstrap passes in a temporary home.
- [ ] AC-02 second apply and plan are no-ops.
- [ ] AC-03 all static assets are individual manifest-owned links.
- [ ] AC-04 unmanaged Codex and skill state is byte-preserved.
- [ ] AC-05 managed config add/change/delete and unmanaged preservation pass.
- [ ] AC-06 snapshot, atomic replacement, rollback, and restore pass.
- [ ] AC-07 status/inventory/list/version JSON contracts pass.
- [ ] AC-08 root `AGENTS.md` is tracked, linked globally, and contains the five required policy sections.
- [ ] AC-09 parallel-review skill and read-only agents pass contract and optional live smoke.
- [ ] AC-10 external reviewer is ephemeral, read-only, bounded, and schema-valid.
- [ ] AC-11 all operational sources and managed links are self-contained; no post-migration sibling-harness inspection occurs.
- [ ] `git diff --check` exits 0.
- [ ] `./tools/run-tests` exits 0 twice from the final source state.
- [ ] Real `codex-harness doctor --json` reports `healthy`.
- [ ] Real `codex-harness plan --json` reports no changes after apply.

## Plan self-review evidence

| Anchor | Result | Evidence |
|---|---|---|
| Q1 intent alignment | PASS | Tasks 1-10 implement the self-contained Codex harness; Task 11 preserves the requested follow-up order. |
| Q2 measurable goals | PASS | AC-01 through AC-11 map to executable checks in Task 10 and the final checklist. |
| Q3 scope completeness | PASS | Global guidance, config, links, cross-machine install, inventory/version, agents, skills, recovery, and follow-up research are covered; non-goals remain excluded. |
| Q4 factual premises | PASS | Codex CLI 0.144.5 and safe current defaults were checked locally; Codex paths, profiles, subagents, rules, and skill locations were checked against current official documentation. |
| L1-a signature consistency | PASS | `Context`, `Asset`, `AssetStatus`, `MergeResult`, and `managed_paths` signatures are used consistently across later tasks. |
| L1-b state/data format | PASS | Manifest assets, state JSON, backup receipt, verdict schema, and JSON command outputs each have one canonical shape. |
| L1-c branch coverage | PASS | Missing/current/broken/drifted/conflict links and pass/changes_requested/blocked verdicts all have explicit branches. |
| L1-d AC test mapping | PASS | Each AC appears in the final checklist and has an owning task plus Task 10 evidence. |
| L1-e stale expression scan | PASS | No removed `sources/guidance` path or pending-review status remains. |
| L1-f version consistency | PASS | Harness `0.1.0`, schema `1`, asset `1.0.0`, and minimum Codex `0.144.5` are consistent. |
| L1-g exact phrase consistency | PASS | Test assertions match the planned guidance headings, statuses, command names, and verdict strings. |
| P1 fact check | PASS | Official Codex manual and observed CLI/config surfaces support the planned locations and flags. |
| P2 cross-file consistency | PASS | File map, manifest targets, tests, command table, docs, and final verification use the same names. |
| P3 spec-to-plan mirror | PASS | The ownership map, command surface, AC count, and two workflow samples match the approved spec. |
| P4 implementation feasibility | PASS | `uv` and Python 3.14 are available; TOML round-trip, temp-home isolation, path approval, Git identity, and pipe environment pitfalls are addressed. |
| P5 legal accuracy | PASS | Adapted ideas are attributed; local skills declare `local-adaptation`; no third-party code is vendored. |
| P6 numeric consistency | PASS | Tasks 1-10 implement 11 ACs; Task 11 is the gated follow-up; external review defaults to two cycles with a hard maximum of three; subagent depth is one and thread cap is four. |
| F1 partial replacement | PASS | Canonical names were globally scanned after edits. |
| F2 cascading rename | PASS | Root `AGENTS.md` replaced the discarded guidance-source path in spec, plan, mapping, and tests. |
| F3 header/body mismatch | PASS | Task count, AC count, command names, and final checklist counts agree. |
| F4 spec/plan mirror omission | PASS | Root guidance ownership and permanent independence boundary appear in both spec and plan. |
| F5 history/context confusion | PASS | Historical migration state is descriptive only; operational commands do not inspect the legacy repository. |
| F6 feasibility omission | PASS | Real-home writes, model-usage smoke tests, PATH, Codex version, secret scanning, and rollback have explicit gates. |
| F7 over-literal fix | PASS | The independence request is implemented as source ownership, doctor validation, link checks, and an always-on policy rather than a single textual warning. |
