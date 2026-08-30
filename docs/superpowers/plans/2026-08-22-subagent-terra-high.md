---
title: Subagent Terra High Implementation Plan
description: Plan for configuring managed custom subagents with terra model assignments and role-specific reasoning effort.
date: 2026-08-22
tags:
  - codex
  - agents
  - configuration
---

# Subagent Terra High Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure all managed custom subagents with `gpt-5.6-terra`, with `high` effort for scanner/developer/verifier and `xhigh` for planner/reviewer.

**Architecture:** The five agent TOML sources define the live configurations because each matching runtime file is a symbolic link to its source. The source-contract test records the expected assignment for each agent.

**Tech Stack:** TOML, Python `unittest`

---

### Task 1: Update the source contract

**Files:**
- Modify: `tests/test_sources.py:131-150`
- Test: `tests/test_sources.py`

- [ ] **Step 1: Change each expected agent pair to the requested configuration**

```python
expected_agents = {
    "scanner": ("gpt-5.6-terra", "high"),
    "planner": ("gpt-5.6-terra", "xhigh"),
    "developer": ("gpt-5.6-terra", "high"),
    "reviewer": ("gpt-5.6-terra", "xhigh"),
    "verifier": ("gpt-5.6-terra", "high"),
}
```

- [ ] **Step 2: Run the focused contract test before the configuration update**

Run: `python3 -m unittest tests.test_sources.SourceTests.test_agent_and_profile_model_assignments`

Expected: FAIL because the five agent TOML files still declare `gpt-5.6-sol`.

### Task 2: Update the managed agent sources

**Files:**
- Modify: `sources/agents/scanner.toml:4-5`
- Modify: `sources/agents/planner.toml:4-5`
- Modify: `sources/agents/developer.toml:4-5`
- Modify: `sources/agents/reviewer.toml:4-5`
- Modify: `sources/agents/verifier.toml:4-5`
- Test: `tests/test_sources.py`

- [ ] **Step 1: Set the model and reasoning effort in every agent source**

```toml
model = "gpt-5.6-terra"
# Use "xhigh" instead for planner and reviewer.
model_reasoning_effort = "high"
```

- [ ] **Step 2: Run the focused contract test after the configuration update**

Run: `python3 -m unittest tests.test_sources.SourceTests.test_agent_and_profile_model_assignments`

Expected: PASS.

- [ ] **Step 3: Verify only the approved agent source files and source contract changed**

Run: `git diff --check && git diff -- tests/test_sources.py sources/agents`

Expected: no whitespace errors; no changes to profiles, root configuration, or the pre-existing `sources/config/config-rock.toml` edit.
