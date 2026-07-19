# Feature Delivery Multi-Agent Workflow Design

**Date:** 2026-07-20  
**Status:** Proposed for written-spec review  
**Scope:** Add planner and developer custom agents plus one reusable feature-delivery skill.

## Context

The harness currently manages three read-only custom agents: scanner, reviewer, and verifier. They form a strong review pipeline, but they do not cover requirements analysis or implementation. The global multi-agent configuration only enables native delegation with a bounded thread count and depth.

Codex already gives the root agent orchestration responsibility. This design therefore adds only the two missing bounded roles and keeps workflow coordination in a skill rather than creating a separate orchestration program.

## Goals

- Add a read-only `planner` agent for requirements, assumptions, risks, dependencies, acceptance criteria, and implementation sequencing.
- Add a workspace-writing `developer` agent for one bounded implementation assignment at a time.
- Add an enabled-by-default `feature-delivery` skill that connects planning, implementation, review, verification, and root integration.
- Preserve root ownership of user communication, scope decisions, commits, pushes, and final integration.
- Allow one developer to edit the active checkout; require a separate Git worktree per developer before parallel write work starts.
- Keep the workflow optional through the existing repository-default and machine-local skill activation controls.

## Non-goals

- Do not build a stateful orchestration daemon or new CLI command.
- Do not replace Codex's root orchestration, built-in agents, or thread controls.
- Do not add designer or test-engineer roles in this change.
- Do not permit subagents to commit, push, approve their own work, or expand scope.
- Do not force the workflow for typos, one-line fixes, or other trivial changes.

## Considered Approaches

### Agent files only

Add planner and developer definitions and depend on task prompts to coordinate them. This is small, but the planning gate, handoff contract, write isolation, and review loop would be repeated inconsistently.

### Agent files plus a workflow skill

Add the two custom agents and a `feature-delivery` skill that defines the lifecycle and communication contract. This reuses Codex-native orchestration while making the workflow portable, inspectable, and versioned. This is the selected approach.

### Stateful orchestration utility

Create a CLI that records stages, agent assignments, and loop state. This could support unattended pipelines later, but it duplicates native thread coordination and is unnecessary for the current interactive/app workflow.

## Components

### Planner agent

`sources/agents/planner.toml` is a read-only custom agent using the demanding Codex model with high reasoning. It receives a bounded planning question and returns:

- objective and explicit non-goals;
- assumptions and unresolved decisions;
- affected paths and dependencies;
- ordered implementation steps;
- risks and mitigations;
- verifiable acceptance criteria.

It does not edit files or silently choose between materially different interpretations.

### Developer agent

`sources/agents/developer.toml` is a workspace-write custom agent using the demanding Codex model with high reasoning. It receives an approved assignment containing scope, owned paths, acceptance criteria, verification commands, and constraints. It:

- changes only assigned paths;
- follows applicable `AGENTS.md` and skill instructions;
- uses test-first development for behavior changes;
- reports changed files, commands run, results, risks, and blockers;
- never commits, pushes, approves, or broadens the assignment.

Only one developer may write in the active checkout. Multiple developers may run in parallel only after the root has assigned each one an isolated worktree and non-overlapping ownership.

### Feature-delivery skill

`sources/skills/feature-delivery/SKILL.md` is the orchestration contract. It applies to non-trivial feature implementation, ambiguous multi-file work, or an explicit multi-agent delivery request. It excludes trivial edits where delegation would add more coordination than value.

The skill is a manifest-managed asset and defaults to enabled. Existing `codex-harness skill enable`, `disable`, and `reset` commands provide the per-machine override.

## Workflow

### 1. Intake

The root states the objective, known constraints, non-goals, acceptance criteria, and unresolved questions. Material ambiguity is raised to the user before implementation.

### 2. Planning and discovery

The root delegates to `planner` and, when repository discovery is needed, `scanner`. They may run in parallel because both are read-only. The planner owns the proposed plan; scanner contributes factual affected-path and dependency evidence.

### 3. Root plan gate

The root reconciles planner and scanner output, checks file references and assumptions, removes unnecessary scope, and publishes the approved implementation assignment. A developer is not spawned until this gate passes.

### 4. Implementation

One `developer` edits the active checkout and runs focused verification. If multiple independent write assignments would materially help, the root first creates one worktree per developer. Concurrent developers never share a writable checkout.

### 5. Independent validation

After implementation stops, `reviewer` and `verifier` run in parallel as read-only agents. Reviewer checks correctness, security, regressions, maintainability, and requirement alignment. Verifier maps each acceptance criterion to fresh test or behavior evidence and distinguishes pass, fail, not-run, and blocked.

### 6. Root reconciliation

The root independently validates actionable findings. Correct findings are returned to the developer as a narrower assignment. The internal implementation-review loop is capped at three cycles. If acceptance criteria still fail after the third cycle, the root reports the evidence and asks for direction rather than looping indefinitely.

### 7. Final integration

The root runs the full relevant verification suite, checks the final diff against the approved scope, and produces the final verdict. Only the root may commit or push, and only when the user's request or existing authorization includes that external state change.

## Handoff Contract

Every delegated prompt includes:

- objective;
- owned scope and excluded scope;
- inputs and known evidence;
- acceptance criteria;
- expected commands or checks;
- expected response format.

Every agent response includes:

- concise outcome;
- files inspected or changed;
- evidence and commands run;
- unresolved risks, uncertainty, or blockers;
- no raw logs unless the root explicitly requests them.

This keeps noisy exploration and test output out of the root context while preserving enough evidence for independent checking.

## Failure and Safety Behavior

- A planner that finds material ambiguity returns alternatives and trade-offs; it does not invent a requirement.
- A developer encountering out-of-scope work stops and reports the dependency.
- A developer encountering a failing baseline distinguishes pre-existing failure from introduced failure and does not claim success.
- A reviewer or verifier finding is advisory until the root validates it.
- Missing worktree isolation blocks parallel developers; the workflow falls back to one developer rather than sharing a checkout.
- Subagents inherit the parent permission boundary, but the custom role files further narrow planner, scanner, reviewer, and verifier to read-only.

## Repository Changes

- Add `sources/agents/planner.toml` and `sources/agents/developer.toml`.
- Add `sources/skills/feature-delivery/SKILL.md` and its skill metadata.
- Register both agents and the skill in `manifest.toml`.
- Bump the harness minor version from `0.2.0` to `0.3.0`.
- Add the non-trivial feature-delivery rule to `AGENTS.md`.
- Update architecture, operations, user guide, README, and source provenance documentation.
- Extend source contract tests for role permissions, manifest entries, workflow stages, write isolation, loop bound, and documentation coverage.

## Verification and Acceptance Criteria

The change is accepted when:

1. All agent TOML files parse and expose non-empty `name`, `description`, and `developer_instructions`.
2. Planner remains read-only and developer is workspace-write.
3. Developer instructions forbid commit, push, scope expansion, and shared-checkout parallel writes.
4. The feature-delivery skill names planner, scanner, developer, reviewer, verifier, and root responsibilities.
5. The skill requires a root plan gate before implementation and isolated worktrees for multiple developers.
6. The skill caps the internal correction loop at three cycles.
7. Manifest targets remain unique and all managed sources exist.
8. The feature-delivery skill is enabled by default and can be toggled with the existing skill commands.
9. Operator documentation explains when the workflow triggers, how to invoke it, and who owns mutations and integration.
10. The full repository test suite passes, `git diff --check` is clean, and a temporary-home harness plan/apply/doctor smoke test recognizes the new assets.
