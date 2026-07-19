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
