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

## Feature Delivery

- Use `$feature-delivery` for non-trivial feature implementation, ambiguous multi-file changes, or explicit multi-agent delivery.
- Start it only from the coordinating root task. As a delegated role in an active feature-delivery workflow, execute the bounded assignment directly; do not re-enter the workflow.
- It is Subagent-Driven by default; a root task-scoped inline override can change execution mode, roles, stage order, or loop count.
- The root validates the plan and retains user communication, commits, pushes, and final integration.
- One developer uses the active checkout; multiple developers require separate worktrees and non-overlapping scope.
- Three cycles are the default; the root may shorten or extend them with evidence.
- The coordinating root owns assigning every handoff label and tool ID: `role instance - task name`; repeatable-role numbers increase monotonically, are never recycled, and only same-thread follow-ups reuse them. Subagents echo their assigned label.
- Skip this workflow for trivial edits.

## Harness Independence

- `codex-helper` is the sole source repository for the Codex harness.
- Never read, search, diff, execute, or modify the sibling Claude harness repository.
- Managed Codex links must resolve inside `codex-helper`; runtime-owned Codex state remains outside Git.
