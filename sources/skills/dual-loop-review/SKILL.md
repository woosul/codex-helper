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
4. Use cycles 3 through 5 only when the preceding cycle found a distinct actionable issue. Never exceed five cycles.
5. On `blocked`, repeated findings, exhausted cycles, or missing authority, stop and report the exact blocker.

## Boundaries

- The external reviewer is ephemeral and read-only.
- Do not use bypass-sandbox flags.
- Do not turn uncertainty or an unavailable test into `pass`.
- Propose persistent `AGENTS.md`, rule, or skill changes separately; require user authorization before changing global policy.
