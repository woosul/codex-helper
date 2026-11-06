---
title: EasyEDA local MCP bridge
description: Official EasyEDA extension API bridge limited to environment reads and a disposable Project1 text test.
date: 2026-10-04
tags: [easyeda, mcp, local-tools]
---

# EasyEDA local MCP bridge

Canonical source: `/Users/denny/Project/codex-helper/tools/easyeda-local-mcp`.
Actual EasyEDA project: `/Users/denny/Project/easyeda/project1-liion-led/Project1-LiIon-LED.eprj2`.
Earlier workspace sources and initial investigation files are preserved in `archive/`. They are historical records, not active launch paths.

Uses EasyEDA Pro 3.2.149's official in-app JavaScript Extension API (bundled API 0.2.53), not an external vendor REST API. Build packaging follows the official [SDK](https://github.com/easyeda/easyeda-api-sdk).

## Scope

`easyeda_environment` returns five environment fields with empty arguments.
`easyeda_project1_control` accepts only a fixed action: read, add_marker, modify_marker, save, delete_marker, restore_marker, reopen. It is restricted to the exact new Project1 P1 page UUID and two fixed test texts. No arbitrary code, file paths, project IDs, circuit primitives, imports, cloud operations or orders are exposed. The bridge itself remains limited to disposable text control. The later authorized circuit and import work will use separately reviewed tools.

## Manual operation

1. Run `node start-bridge.mjs` from this directory using `/Users/denny/.nvm/versions/node/v22.23.1/bin/node`. No login service is installed. Listener: `127.0.0.1:18149/easyeda` only; private IPC: `.runtime/bridge.sock`.
2. In EasyEDA, import `artifacts/codex-environment-bridge_v0.2.2.eext` through Advanced → Extensions Manager. Use the existing extension UUID and previously approved External Interactions permission.
3. Select Local Environment → Connect local bridge. Enter the current temporary `.runtime/pairing-code` in the masked field. Never print it in chat or logs. Runtime directory is 0700; code/socket/log files are private.
4. `node project1-probe.mjs read` verifies the actual stdio MCP tool catalog, rejects extra arguments, and queries the fixed open page. Results are written to `artifacts/`.
5. Before replacing an extension package, choose Disconnect local bridge. Close stale WebSockets before importing an update; the installed client's unload path may otherwise remove menus before completing installation.
6. To stop, verify that the PID from `.runtime/bridge.pid` belongs to this directory's bridge-daemon.mjs, then send SIGTERM. Restart requires pairing with a new code.

`mcp-server.mjs` is registered as `easyeda_local_environment` in the rock canonical host config and current live config. The live config was a regular file; recorded helper state declared kind=copy. Its topology and unrelated user settings were preserved. Private pre-relocation backups are under Git-ignored `.runtime/config-backups/`. No blanket harness apply or configuration regeneration was performed.

## Evidence and limits

Stage 1 actual environment reads succeeded. Early Project1 add/save/read succeeded, but version 0.2.0 modify/delete results did not survive read/reopen; those results are not a completed edit test. Version 0.2.1 passes string primitive IDs and verifies resulting content/count. See current artifacts for fresh results; archive records are historical.

The native Codex tool catalog in this task has no EasyEDA tool. Actual MCP verification uses the official SDK's stdio client and the real app. Desktop MCP registration alone is not evidence of a native tool call.

`node security-test.mjs` is a synthetic protocol test and does not edit user designs. Dependencies are pinned and were installed from the standard registry with scripts disabled. No community MCP, debugging port, regional client change or KiCad import is involved.

## Latest result, 2026-10-04

Fresh evidence: `artifacts/v0.2.2-persistence-verification.json`. Extension 0.2.2 was imported with the same UUID and existing permissions. Create, replacement, and delete each survived save → closeDocument → openDocument → fresh getAll. A final independent stdio read confirmed zero markers.

The dedicated `sch_PrimitiveText.delete` failed this persistence test in 0.2.1. The public `sch_PrimitiveObject.delete` succeeds. The upstream reproduction and fix are described in [easyeda-agent issue 164](https://github.com/zhoushoujianwork/easyeda-agent/issues/164). Installed API 0.2.53 exposes this generic delete route. No private editor internals were changed or invoked.

Text modification uses create + generic delete. The primitive ID changes: `603337e32558408b` → `7799e5976de37c64`. The new content and x/y persisted after document reopen. This does not prove in-place text modification, app restart recovery, or persistence of other primitive types.

Project1 is blank apart from its default drawing frame after the test. The own bridge is still limited to this page and fixed marker operations. Broader circuit work and the separately installed community tool have not yet been verified. Native Codex tool invocation is not verified; these runs use the official MCP SDK stdio client and the real EasyEDA app.
