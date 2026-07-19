# Feature Delivery Multi-Agent Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add planner and developer custom agents and an enabled-by-default feature-delivery skill that orchestrates planning, bounded implementation, independent validation, and root-owned integration.

**Architecture:** Keep orchestration in a reusable Codex skill, role restrictions in standalone agent TOML files, and durable triggering/write-ownership rules in `AGENTS.md`. Reuse the existing manifest, per-machine skill activation, native subagent threads, reviewer, verifier, scanner, and root agent rather than adding a new runtime or CLI.

**Tech Stack:** TOML agent and manifest configuration, Markdown Codex skills and guidance, YAML skill interface metadata, Python `unittest`, shell-based harness smoke tests.

---

## File Map

- Create `sources/agents/planner.toml`: read-only planning role and response contract.
- Create `sources/agents/developer.toml`: bounded workspace-write implementation role.
- Modify `sources/agents/scanner.toml`: add a readable singleton nickname.
- Modify `sources/agents/reviewer.toml`: add readable numbered reviewer nicknames.
- Modify `sources/agents/verifier.toml`: add readable numbered verifier nicknames.
- Create `sources/skills/feature-delivery/SKILL.md`: orchestration stages, handoffs, write isolation, and correction bound.
- Create `sources/skills/feature-delivery/agents/openai.yaml`: user-facing skill metadata and default prompt.
- Modify `manifest.toml`: register the two agents and togglable skill; bump harness version.
- Modify `AGENTS.md`: make the workflow the durable default for non-trivial feature work.
- Modify `tests/test_sources.py`: source, role, manifest, skill, and documentation contracts.
- Modify `tests/test_harness.py`: expected harness version.
- Modify `README.md`: advertise the workflow and invocation.
- Modify `docs/architecture.md`: document roles, data flow, and write ownership.
- Modify `docs/user-guide.md`: explain invocation, stages, and skill ON/OFF behavior.
- Modify `docs/operations.md`: document safe operation and failure handling.
- Modify `docs/sources.md`: record official provenance and local adaptation.

### Task 1: Establish the agent and manifest contracts

**Files:**
- Modify: `tests/test_sources.py`
- Modify: `tests/test_harness.py`
- Create: `sources/agents/planner.toml`
- Create: `sources/agents/developer.toml`
- Modify: `manifest.toml`

- [ ] **Step 1: Write failing source and version tests**

In `tests/test_sources.py`, add the two new agent paths to `test_manifest_and_toml_sources_parse`, replace `test_agents_are_named_and_read_only` with the permission-aware contract below, and change the skill-activation version assertion to `0.3.0`:

```python
    def test_agents_have_declared_role_permissions(self):
        expected_modes = {
            "scanner": "read-only",
            "planner": "read-only",
            "developer": "workspace-write",
            "reviewer": "read-only",
            "verifier": "read-only",
        }
        for name, sandbox_mode in expected_modes.items():
            with self.subTest(name=name):
                data = tomllib.loads((ROOT / f"sources/agents/{name}.toml").read_text())
                self.assertEqual(name, data["name"])
                self.assertEqual(sandbox_mode, data["sandbox_mode"])
                self.assertTrue(data["description"])
                self.assertTrue(data["developer_instructions"])

    def test_feature_delivery_manifest_contract(self):
        data = tomllib.loads((ROOT / "manifest.toml").read_text())
        self.assertEqual("0.3.0", data["harness_version"])
        assets = {asset["id"]: asset for asset in data["assets"]}
        expected = {
            "agent-planner": (
                "agents",
                "sources/agents/planner.toml",
                "${CODEX_HOME:-$HOME/.codex}/agents/planner.toml",
            ),
            "agent-developer": (
                "agents",
                "sources/agents/developer.toml",
                "${CODEX_HOME:-$HOME/.codex}/agents/developer.toml",
            ),
            "skill-feature-delivery": (
                "skills",
                "sources/skills/feature-delivery",
                "$HOME/.agents/skills/feature-delivery",
            ),
        }
        for asset_id, (category, source, target) in expected.items():
            with self.subTest(asset_id=asset_id):
                asset = assets[asset_id]
                self.assertEqual(category, asset["category"])
                self.assertEqual(source, asset["source"])
                self.assertEqual(target, asset["target"])
        self.assertTrue(assets["skill-feature-delivery"]["enabled"])
```

In `tests/test_harness.py`, change both literal expected harness versions from `0.2.0` to `0.3.0`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run python -m unittest tests.test_sources.SourceContractTests.test_agents_have_declared_role_permissions tests.test_sources.SourceContractTests.test_feature_delivery_manifest_contract tests.test_harness.HarnessTests.test_plan_is_read_only_and_lists_declared_assets tests.test_harness.HarnessTests.test_utilities_are_manifest_managed -v
```

Expected: FAIL because `planner.toml`, `developer.toml`, and the manifest entries do not exist and the manifest still reports `0.2.0`.

- [ ] **Step 3: Add the planner and developer agent files**

Create `sources/agents/planner.toml`:

```toml
name = "planner"
description = "Read-only requirements analyst and implementation planner for non-trivial feature work."
model = "gpt-5.6-sol"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = """
Analyze only the assigned objective. Do not edit files, commit, push, or silently resolve material ambiguity.
Return objective, non-goals, assumptions, unresolved decisions, affected paths, dependencies, ordered steps, risks, and verifiable acceptance criteria.
Distinguish repository evidence from inference and keep the plan within the requested scope.
"""
```

Create `sources/agents/developer.toml`:

```toml
name = "developer"
description = "Bounded implementation worker for an approved plan and explicitly owned paths."
model = "gpt-5.6-sol"
model_reasoning_effort = "high"
sandbox_mode = "workspace-write"
developer_instructions = """
Implement only the approved assignment and owned paths. Follow applicable AGENTS.md and skill instructions and use test-first development for behavior changes.
Do not broaden scope, commit, push, approve your own work, or overwrite unrelated user changes.
Only one developer may write in a checkout. Refuse parallel shared-checkout writes and require a separate worktree per developer.
Return the outcome, changed files, commands and results, risks, uncertainty, and blockers to the root agent.
"""
```

- [ ] **Step 4: Register assets and bump the harness version**

Change the top-level manifest version:

```toml
harness_version = "0.3.0"
```

Add these agent assets after the scanner entry:

```toml
[[assets]]
id = "agent-planner"
kind = "symlink"
category = "agents"
source = "sources/agents/planner.toml"
target = "${CODEX_HOME:-$HOME/.codex}/agents/planner.toml"
scope = "global"
version = "1.0.0"

[[assets]]
id = "agent-developer"
kind = "symlink"
category = "agents"
source = "sources/agents/developer.toml"
target = "${CODEX_HOME:-$HOME/.codex}/agents/developer.toml"
scope = "global"
version = "1.0.0"
```

Add this skill asset after the existing review skills:

```toml
[[assets]]
id = "skill-feature-delivery"
kind = "symlink"
category = "skills"
enabled = true
source = "sources/skills/feature-delivery"
target = "$HOME/.agents/skills/feature-delivery"
scope = "global"
version = "1.0.0"
upstream = "https://learn.chatgpt.com/docs/agent-configuration/subagents"
license = "local-adaptation"
last_reviewed = "2026-07-20"
```

- [ ] **Step 5: Run focused and manifest regression tests and verify GREEN**

Run:

```bash
uv run python -m unittest tests.test_sources tests.test_harness -v
```

Expected: PASS, with unique agent/skill targets and `0.3.0` in plan/version output.

- [ ] **Step 6: Commit the role and manifest layer**

```bash
git add tests/test_sources.py tests/test_harness.py sources/agents/planner.toml sources/agents/developer.toml manifest.toml
git commit -m "feat: add planner and developer agents"
```

### Task 2: Define the feature-delivery workflow contract

**Files:**
- Modify: `tests/test_sources.py`
- Create: `sources/skills/feature-delivery/SKILL.md`
- Create: `sources/skills/feature-delivery/agents/openai.yaml`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write the failing workflow contract test**

Add this test to `tests/test_sources.py`:

```python
    def test_feature_delivery_skill_contract(self):
        skill = ROOT / "sources/skills/feature-delivery/SKILL.md"
        metadata = ROOT / "sources/skills/feature-delivery/agents/openai.yaml"
        text = skill.read_text()
        for phrase in (
            "name: feature-delivery",
            "planner",
            "scanner",
            "developer",
            "reviewer",
            "verifier",
            "root plan gate",
            "Subagent-Driven by default",
            "inline workflow override",
            "separate worktree per developer",
            "three-cycle default",
            "add, remove, reorder, or skip",
            "root agent owns commits, pushes, and final integration",
        ):
            self.assertIn(phrase, text)
        self.assertIn("Feature Delivery", metadata.read_text())
        guidance = (ROOT / "AGENTS.md").read_text()
        self.assertIn("$feature-delivery", guidance)
        self.assertIn("non-trivial feature", guidance)
```

- [ ] **Step 2: Run the workflow test and verify RED**

Run:

```bash
uv run python -m unittest tests.test_sources.SourceContractTests.test_feature_delivery_skill_contract -v
```

Expected: ERROR or FAIL because the new skill files and durable guidance do not exist.

- [ ] **Step 3: Create the orchestration skill**

Create `sources/skills/feature-delivery/SKILL.md`:

```markdown
---
name: feature-delivery
description: Use for non-trivial feature implementation, ambiguous multi-file changes, or an explicit multi-agent delivery request. Skip typos, one-line fixes, and other trivial changes.
---

# Feature Delivery

## Execution Strategy

- Use Subagent-Driven by default when the task does not select an execution strategy.
- The root may provide an explicit inline workflow override for one task to execute directly; add, remove, reorder, or skip roles and stages; or change the correction-loop count.
- This is a default playbook, not an immutable state machine. System and user permission boundaries still apply.

## Entry Guard

- Start this workflow only from the coordinating root task.
- When dispatched as a role within an active feature-delivery workflow, execute the bounded assignment directly; do not re-enter this workflow.

1. Restate the objective, constraints, non-goals, acceptance criteria, and unresolved questions.
2. Spawn `planner` and, when repository discovery is needed, `scanner`. They are read-only and may run in parallel.
3. Apply the root plan gate: reconcile evidence, verify paths and assumptions, remove unnecessary scope, and publish one approved developer assignment.
4. Spawn one `developer` in the active checkout. Provide owned paths, excluded scope, acceptance criteria, and verification commands.
5. For multiple developers, create and assign a separate worktree per developer before spawning them. Never allow concurrent developers to share a writable checkout.
6. After implementation stops, spawn `reviewer` and `verifier` in parallel. Wait for both and independently validate every actionable finding.
7. Return validated findings to the developer as a narrower assignment, then rerun reviewer and verifier checks. Use a three-cycle default stop point; the root may shorten or extend it when task evidence warrants the change.
8. Run final verification and inspect the final diff. The root agent owns commits, pushes, and final integration, subject to the user's authorization.

## Handoff Contract

Every assignment includes objective, owned and excluded scope, inputs, acceptance criteria, expected checks, and expected response format.

Every response includes outcome, files inspected or changed, commands and evidence, risks, uncertainty, and blockers. Return summaries rather than raw logs unless the root requests them.

## Boundaries

- Material ambiguity returns to the root or user before implementation.
- Subagents never commit, push, approve their own work, or expand scope.
- A shared-checkout write conflict falls back to one developer until worktree isolation exists.
- The root rechecks subagent evidence and resolves contradictions.
- Inline overrides do not transfer root-owned commit, push, or final-integration authority and do not permit multiple developers to write in one checkout.
- Keep the delegating parent/root task persistent until every spawned subagent has returned.
```

Create `sources/skills/feature-delivery/agents/openai.yaml`:

```yaml
interface:
  display_name: "Feature Delivery"
  short_description: "Plan, implement, review, and verify a bounded feature"
  default_prompt: "Deliver this feature through planner/scanner discovery, a root plan gate, one bounded developer, and independent reviewer/verifier checks."
```

- [ ] **Step 4: Add the durable trigger and ownership rule**

Append this section to `AGENTS.md` before `Harness Independence`:

```markdown
## Feature Delivery

- Use `$feature-delivery` for non-trivial feature implementation, ambiguous multi-file changes, or an explicit multi-agent delivery request.
- Use Subagent-Driven execution by default. The root may replace it for one task with an explicit inline workflow override that changes execution mode, roles, stage order, or loop count.
- When dispatched as a role inside an active feature-delivery workflow, execute the assigned role directly and do not re-enter `$feature-delivery`.
- The root validates the plan before delegating implementation and retains user communication, commits, pushes, and final integration.
- One developer may write in the active checkout. Multiple developers require a separate worktree and non-overlapping ownership for each developer.
- Three cycles is the default correction stop point; the root may shorten or extend it when task evidence warrants the change.
- Skip the workflow for typos, one-line fixes, and other trivial changes.
```

- [ ] **Step 5: Run workflow and full source tests and verify GREEN**

Run:

```bash
uv run python -m unittest tests.test_sources -v
```

Expected: PASS, including the new workflow contract.

- [ ] **Step 6: Commit the workflow layer**

```bash
git add tests/test_sources.py sources/skills/feature-delivery AGENTS.md
git commit -m "feat: add feature delivery workflow"
```

### Task 3: Add visible subagent role badges

**Files:**
- Modify: `tests/test_sources.py`
- Modify: `sources/agents/scanner.toml`
- Modify: `sources/agents/planner.toml`
- Modify: `sources/agents/developer.toml`
- Modify: `sources/agents/reviewer.toml`
- Modify: `sources/agents/verifier.toml`
- Modify: `sources/skills/feature-delivery/SKILL.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Write the failing visibility contract test**

Extend the agent role test to require non-empty unique `nickname_candidates` for every managed agent. Require singleton `Planner` and `Scanner` names and numbered `Developer 1`, `Reviewer 1`, and `Verifier 1` names.

Extend `test_feature_delivery_skill_contract` with these exact portable display contracts:

```python
        for phrase in (
            "planner - plan feature delivery",
            "developer 1 - implement role badges",
            "reviewer 1 - review role spec",
            "reviewer 2 - review role quality",
            "verifier 1 - verify acceptance criteria",
            "reviewer_2__review_role_quality",
            "numbers increase monotonically",
            "follow-up to the same thread reuses",
            "Subagents echo the assigned label",
            "dispatch, progress, and completion",
        ):
            self.assertIn(phrase, text)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
uv run python -m unittest tests.test_sources.SourceContractTests.test_agents_have_declared_role_permissions tests.test_sources.SourceContractTests.test_feature_delivery_skill_contract -v
```

Expected: FAIL because nickname candidates and the visibility contract are absent.

- [ ] **Step 3: Add nickname candidates and the portable badge contract**

Add nickname candidates to the five agent TOML files:

```toml
nickname_candidates = ["Scanner"]
nickname_candidates = ["Planner"]
nickname_candidates = ["Developer 1", "Developer 2", "Developer 3"]
nickname_candidates = ["Reviewer 1", "Reviewer 2", "Reviewer 3"]
nickname_candidates = ["Verifier 1", "Verifier 2", "Verifier 3"]
```

Place the matching line in each role file; do not combine them into one file.

Add a `Visibility Contract` section to the feature-delivery skill. Require the root to assign `role instance - verb-object task name` labels such as `planner - plan feature delivery`, `developer 1 - implement role badges`, `reviewer 1 - review role spec`, `reviewer 2 - review role quality`, and `verifier 1 - verify acceptance criteria`. Keep the same label on dispatch, progress, and completion updates. Repeatable-role numbers increase monotonically for each distinct spawned thread and are never recycled; a follow-up to the same thread reuses its number. Subagents echo the root-assigned label and never allocate numbers. Require matching tool-compatible task IDs such as `reviewer_2__review_role_quality`.

Add a concise `AGENTS.md` rule requiring the root-assigned portable role/task label on every subagent dispatch and status summary.

- [ ] **Step 4: Run the source and harness tests and verify GREEN**

Run:

```bash
uv run python -m unittest tests.test_sources tests.test_harness -v
git diff --check
```

Expected: PASS with all role names and badge strings covered.

- [ ] **Step 5: Commit the visibility layer**

```bash
git add tests/test_sources.py sources/agents sources/skills/feature-delivery/SKILL.md AGENTS.md
git commit -m "feat: expose subagent role badges"
```

### Task 4: Document operation and activation

**Files:**
- Modify: `tests/test_sources.py`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/user-guide.md`
- Modify: `docs/operations.md`
- Modify: `docs/sources.md`

- [ ] **Step 1: Write the failing documentation contract test**

Add this test to `tests/test_sources.py`:

```python
    def test_operator_docs_cover_feature_delivery(self):
        documents = {
            "README": (ROOT / "README.md").read_text(),
            "architecture": (ROOT / "docs/architecture.md").read_text(),
            "user-guide": (ROOT / "docs/user-guide.md").read_text(),
            "operations": (ROOT / "docs/operations.md").read_text(),
            "sources": (ROOT / "docs/sources.md").read_text(),
        }
        for name, text in documents.items():
            with self.subTest(document=name):
                self.assertIn("feature-delivery", text)
        guide = documents["user-guide"]
        for phrase in ("planner", "developer", "기본 Subagent-Driven", "인라인 override", "별도 worktree", "기본 세 번"):
            self.assertIn(phrase, guide)
        operations = documents["operations"]
        self.assertIn("codex-harness skill disable feature-delivery", operations)
        self.assertIn("commit과 push", operations)
```

- [ ] **Step 2: Run the documentation test and verify RED**

Run:

```bash
uv run python -m unittest tests.test_sources.SourceContractTests.test_operator_docs_cover_feature_delivery -v
```

Expected: FAIL because the operator documents do not mention the new workflow.

- [ ] **Step 3: Update README and architecture documentation**

Add a `Feature delivery workflow` section to `README.md` with `$feature-delivery`, the seven-stage summary, trivial-change exclusion, and a link to the user guide.

In `docs/architecture.md`, replace the review-only workflow section with an agent-workflow section that records:

```text
planner/scanner -> root plan gate -> developer -> reviewer/verifier -> root integration
```

State that planner/scanner/reviewer/verifier are read-only, developer is workspace-write, the root owns final authority, and parallel developers require separate worktrees.

- [ ] **Step 4: Update user and operator guidance**

In `docs/user-guide.md`, add `기능 전달 워크플로` before `네이티브 병렬 리뷰`. Include:

```text
$feature-delivery
planner/scanner → 루트 계획 검증 → developer → reviewer/verifier → 루트 통합
```

Explain default Subagent-Driven execution, the root's task-scoped inline override, one active-checkout developer, separate worktrees for multiple developers, the three-cycle default, and root-owned commit/push. State that the root may add, remove, reorder, or skip stages and change the loop count, while commit/push/final integration and multi-developer worktree ownership remain fixed.

In `docs/operations.md`, add invocation, health inspection, `codex-harness skill disable feature-delivery`, `enable`, and `reset`, plus the rule that commit and push remain root-only and authorization-bound.

In `docs/sources.md`, add `feature-delivery` to the local adaptations derived from the official Subagents guidance.

- [ ] **Step 5: Run the documentation and source contracts and verify GREEN**

Run:

```bash
uv run python -m unittest tests.test_sources -v
```

Expected: PASS with every operator document covering the workflow.

- [ ] **Step 6: Commit the documentation layer**

```bash
git add tests/test_sources.py README.md docs/architecture.md docs/user-guide.md docs/operations.md docs/sources.md
git commit -m "docs: document feature delivery operation"
```

### Task 5: Verify harness convergence and finish the branch

**Files:**
- Modify: `docs/superpowers/plans/2026-07-20-feature-delivery.md`

- [ ] **Step 1: Run the full repository suite**

Run:

```bash
./tools/run-tests
git diff --check
```

Expected: all tests pass and no whitespace errors.

- [ ] **Step 2: Smoke the new assets in an isolated home**

Run each command from the feature worktree using the same `HARNESS_SMOKE_HOME` value:

```bash
HARNESS_SMOKE_HOME="$(mktemp -d)"
env HOME="$HARNESS_SMOKE_HOME" CODEX_HOME="$HARNESS_SMOKE_HOME/.codex" ./bin/codex-harness --host default bootstrap
env HOME="$HARNESS_SMOKE_HOME" CODEX_HOME="$HARNESS_SMOKE_HOME/.codex" ./bin/codex-harness --host default plan --json
env HOME="$HARNESS_SMOKE_HOME" CODEX_HOME="$HARNESS_SMOKE_HOME/.codex" ./bin/codex-harness --host default apply --yes
env HOME="$HARNESS_SMOKE_HOME" CODEX_HOME="$HARNESS_SMOKE_HOME/.codex" ./bin/codex-harness --host default skill status feature-delivery --json
env HOME="$HARNESS_SMOKE_HOME" CODEX_HOME="$HARNESS_SMOKE_HOME/.codex" ./bin/codex-harness --host default doctor --json
```

Expected: plan includes `agent-planner`, `agent-developer`, and `skill-feature-delivery`; apply succeeds; skill status is `current` and effectively enabled; doctor reports `healthy`.

- [ ] **Step 3: Exercise the local feature-delivery toggle**

Run with the same isolated home:

```bash
env HOME="$HARNESS_SMOKE_HOME" CODEX_HOME="$HARNESS_SMOKE_HOME/.codex" ./bin/codex-harness --host default skill disable feature-delivery --json
env HOME="$HARNESS_SMOKE_HOME" CODEX_HOME="$HARNESS_SMOKE_HOME/.codex" ./bin/codex-harness --host default doctor --json
env HOME="$HARNESS_SMOKE_HOME" CODEX_HOME="$HARNESS_SMOKE_HOME/.codex" ./bin/codex-harness --host default skill reset feature-delivery --json
env HOME="$HARNESS_SMOKE_HOME" CODEX_HOME="$HARNESS_SMOKE_HOME/.codex" ./bin/codex-harness --host default plan --json
```

Expected: disable reports an intentional healthy disabled state; reset removes the local override; the final plan has no changes.

- [ ] **Step 4: Review final scope and record completion**

Run:

```bash
git status --short
git diff master...HEAD --stat
git diff master...HEAD -- AGENTS.md manifest.toml sources tests README.md docs
```

Expected: every changed implementation line traces to the approved feature-delivery design, with no unrelated files.

Mark completed plan steps with `[x]`, then run `git diff --check`.

- [ ] **Step 5: Commit the completed verification record**

```bash
git add docs/superpowers/plans/2026-07-20-feature-delivery.md
git commit -m "docs: record feature delivery verification"
```
