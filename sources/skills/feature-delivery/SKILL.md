---
name: feature-delivery
description: >-
  Use only when the user explicitly invokes $feature-delivery or explicitly
  asks to use the feature-delivery workflow. Never auto-trigger from task size,
  ambiguity, file count, or implementation complexity.
---

# Feature Delivery

## Activation Gate

Start this workflow only from the coordinating root task and only when the user explicitly requests it. Mentioning feature delivery as a topic or editing this skill is not an invocation. When dispatched as a role within an active feature-delivery workflow, execute the bounded assignment directly; do not re-enter this workflow.

## Execution Strategy

Use **Root-Inline by default**. The root agent plans, implements, reviews, and verifies the work directly.

Invoking `$feature-delivery` authorizes the root to spawn subagents as needed and does not require a separate subagent request. This is permission, not a requirement; the root may still keep the workflow inline.

If the root spawns a subagent, the delegated scope transfers to that subagent. Once the root delegates a bounded task, that subagent owns and performs it; the root must not duplicate the delegated work while it is active. The root may continue coordination, integration, or clearly non-overlapping work.

The root may **add, remove, reorder, or skip** roles or stages and may change the correction-loop count. System and user permission boundaries still apply.

## Default Root-Inline Playbook

1. Restate the objective, constraints, acceptance criteria, and unresolved questions.
2. Inspect the repository directly and apply a **root plan gate** before editing.
3. Implement the smallest valid change in the active checkout.
4. Run focused tests, then fresh final verification.
5. Review the final diff and report remaining uncertainty.

## Authorized Subagent-Driven Variant

Use this variant after an explicit `$feature-delivery` invocation when the root chooses delegation, or after a separate explicit request for subagents.

1. Run `planner` and, when repository discovery helps, `scanner` as bounded read-only assignments.
2. Apply the root plan gate and assign one `developer` an explicit scope and required tests.
3. Do not require a separate worktree for a single developer or sequential developer assignments unless the root explicitly requests one. Before starting a second concurrent developer, verify that it has a separate worktree; create one before work begins if it does not. Concurrent developers must not share a writable checkout.
4. Run `reviewer` and `verifier` after implementation.
5. Return validated findings to the developer as a narrower assignment. The **three-cycle default** may be shortened or extended by the root with evidence.
6. Perform final root verification and integration.

## Handoff Contract

For every explicit assignment, supply the objective, acceptance criteria, owned and excluded paths, constraints, expected checks, and response format. Treat the assignment as exclusive while active: the subagent performs the delegated work and the root does not implement the same scope. The root rechecks returned evidence before integration.

## Visibility Contract

The coordinating root assigns a label and tool task ID to every explicit handoff:

- `planner - plan feature delivery`
- `developer 1 - implement role badges`
- `reviewer 1 - review role spec`
- `reviewer 2 - review role quality`
- `verifier 1 - verify acceptance criteria`

Repeatable-role numbers increase monotonically and are never recycled. Only a follow-up to the same agent thread reuses its number. Tool task IDs mirror the label, for example `reviewer_2__review_role_quality`. Subagents echo the assigned label and never allocate numbers.

## Boundaries

- Return material ambiguity to the root; do not expand scope.
- Subagents do not commit, push, self-approve, or broaden their assignment.
- The root must not duplicate the delegated work; it resumes that scope only after completion, interruption, or a reported blocker.
- The delegating parent/root task remains persistent until every spawned subagent has returned.
- The root agent owns commits, pushes, and final integration.
