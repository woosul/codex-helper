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

## 5. Trade-off Reporting

- End every decision recommendation and non-trivial work result with a clearly labeled `Trade-off:` statement, or `트레이드오프:` when responding in Korean.
- State the concrete benefit together with the cost, constraint, risk, or forgone alternative that materially affects the decision.
- Exclude simple work results, factual answers, acknowledgements, and status-only responses. Do not invent a trade-off when none materially exists.

## Codex Operating Rules

- Use `AGENTS.md` for durable behavior, skills for reusable workflows, custom agents for bounded roles, and rules for command policy.
- The root handles tasks directly by default. Use subagents only when the user explicitly requests subagents, delegation, multi-agent execution, or parallel agent work, or explicitly invokes `$feature-delivery`.
- Preserve user changes and external tool-managed state unless the user explicitly places them in scope.

## Feature Delivery

- Only invoke `$feature-delivery` when the user explicitly requests it. Do not infer activation from task size, ambiguity, file count, or implementation complexity.
- Merely mentioning the skill, quoting its name, or editing its contract is not an invocation.
- If `$feature-delivery` is unavailable or disabled, the coordinating root may execute or reconfigure the workflow inline or use another chosen workflow; it must not attempt to invoke the missing skill.
- The remaining rules in this section apply only while a feature-delivery workflow is active.
- Start it only from the coordinating root task. As a delegated role in an active feature-delivery workflow, execute the bounded assignment directly; do not re-enter the workflow.
- It is Root-Inline by default, but an active explicit invocation authorizes subagents without a separate request.
- Once the root delegates a bounded task, the subagent owns and performs that scope. The root must not duplicate the delegated work and may continue only coordination, integration, or clearly non-overlapping work.
- The root validates the plan and retains user communication, commits, pushes, and final integration.
- Do not require a separate worktree for one developer or sequential developer assignments unless the root explicitly asks for one. Before starting a second concurrent developer, verify isolation and create one before dispatch if needed; concurrent developers must not share a writable checkout.
- Five cycles are the default; the root may shorten or extend them with evidence.
- The coordinating root owns assigning every handoff label and tool ID: `role instance - task name`; repeatable-role numbers increase monotonically, are never recycled, and only same-thread follow-ups reuse them. Subagents echo their assigned label.

## Documentation

- New Markdown documents must start with YAML frontmatter containing `title`, `description`, `date`, and `tags`.
- When directly updating a maintained Markdown document that lacks frontmatter, add it if doing so is within the requested scope.
- Do not rewrite generated artifacts or vendored upstream documents solely to add frontmatter.

## Harness Independence

- `codex-helper` is the sole source repository for the Codex harness.
- Read-only inspection of the sibling Claude harness requires explicit user approval. After approval, reading, searching, and diffing are allowed within the approved scope.
- Executing or modifying the sibling Claude harness requires separate explicit user authorization.
- Managed Codex links must resolve inside `codex-helper`; runtime-owned Codex state remains outside Git.
