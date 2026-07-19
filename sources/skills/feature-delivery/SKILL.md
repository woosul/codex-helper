---
name: feature-delivery
description: Use for non-trivial feature implementation, ambiguous multi-file changes, or explicit multi-agent delivery. Skip typos, one-line changes, and other trivial edits.
---

# Feature Delivery

## Execution Strategy

Start this workflow only from the coordinating root task. When dispatched as a role within an active feature-delivery workflow, do not re-enter this workflow; execute the bounded assignment directly.

Use **Subagent-Driven by default** when the task does not select an execution strategy. The root agent may provide an explicit **inline workflow override** to execute directly, to **add, remove, reorder, or skip** roles or stages, or to change the correction-loop count. This is a default playbook, not an immutable state machine. System and user permission boundaries still apply.

## Default Playbook

1. Restate the objective, constraints, non-goals, acceptance criteria, and unresolved questions.
2. Run `planner` and, when repository discovery helps, `scanner` as bounded read-only work in parallel.
3. Apply a **root plan gate**: reconcile their evidence, resolve or return material ambiguity, and approve the assignment before any implementation begins.
4. Assign one `developer` an active checkout, explicit owned and excluded scope, and required tests. A developer works test-first and reports fresh evidence.
5. Before spawning multiple developers, create **a separate worktree per developer**. Developers may not share a writable checkout; their scopes must not overlap.
6. Run `reviewer` and `verifier` in parallel after implementation, then wait for both. The root validates each finding before correction.
7. Return validated findings to the developer as a narrower assignment, then rerun the `reviewer` and `verifier` checks through the **three-cycle default**. Direct root correction is available only through an explicit inline override. The root may shorten or extend the loop when the evidence supports it.
8. Perform final root verification and inspect the final diff.

## Handoff Contract

Every assignment supplies: the objective, acceptance criteria, owned paths, excluded paths, relevant constraints, the expected tests or checks, and the required response format. Each response summarizes changed paths or inspected evidence, commands run with outcomes, findings, unresolved ambiguity, and any scope concern. The root rechecks evidence before relying on it.

## Boundaries

- Return material ambiguity to the root for resolution; do not guess or expand scope.
- Subagents do not commit, push, self-approve, or expand the assigned scope.
- A shared-write conflict falls back to one developer.
- An inline override cannot transfer root-owned commits, pushes, or final integration, and cannot allow multiple developers in one checkout.
- The delegating parent/root task remains persistent until every spawned subagent has returned; use a persistent app task or interactive CLI.
- The root agent owns commits, pushes, and final integration.
