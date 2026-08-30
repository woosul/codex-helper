---
title: Subagent Terra High Configuration
description: Configure every managed custom subagent to use gpt-5.6-terra with high reasoning effort.
date: 2026-08-22
tags:
  - codex
  - agents
  - configuration
---

# Subagent Terra High Configuration

## Scope

Set `model = "gpt-5.6-terra"` in each managed custom-agent source. Set `model_reasoning_effort = "high"` for scanner, developer, and verifier; set it to `"xhigh"` for planner and reviewer. Update the source-contract test to assert those same assignments.

## Exclusions

Do not change the root configuration, profile configurations, agent permissions, agent instructions, or the existing user change in `sources/config/config-rock.toml`.

## Verification

The targeted source test must pass. The managed runtime agent files are symbolic links to these sources, so source changes are the runtime changes.
