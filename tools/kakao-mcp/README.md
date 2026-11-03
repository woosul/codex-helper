---
title: KakaoTalk MCP installation and maintenance
description: Pinned community MCP setup for Claude Code and Codex with a local account recovery fix.
date: 2026-11-03
tags:
  - kakaotalk
  - mcp
  - macos
---

# KakaoTalk MCP

This installs the existing `Jaeha0526/kakao-mcp` server. Reading uses the local KakaoTalk database; optional sending uses `kmsg` Accessibility automation. Sending starts disabled and requires an explicit recipient allowlist plus prepare/confirm calls.

## Pinned sources

| Component | Repository | Commit |
|---|---|---|
| MCP server | https://github.com/Jaeha0526/kakao-mcp | `028588f447536ae4f9b06f54dbf2c876246292cc` |
| DB reader | https://github.com/Jaeha0526/kakaocli | `2c74e63d2c8846c50d8eb1895eb6d835bfef4bc9` |
| Optional sender | https://github.com/channprj/kmsg | `54cbff790b409214735ef365a621d791034fe500` |

`kakaocli-account-recovery.patch` modifies the reader and adds regression tests. The upstream reader license is retained in `UPSTREAM-LICENSE`.

## Install on a new Mac

Prerequisites: macOS, a logged-in KakaoTalk Mac app, Homebrew, uv, and Xcode Command Line Tools. Runtime files stay outside Git under `~/.local/share/kakao-mcp`.

```sh
bash tools/kakao-mcp/install.sh
claude mcp add kakao --scope user -- "$HOME/.local/share/kakao-mcp/server/.venv/bin/kakao-mcp"
```

ROCK and GEMS source configurations declare the same Codex `mcp_servers.kakao` entry. Apply only that entry to the active Codex configuration when other local settings are in progress. For an unmanaged Codex configuration, register it with:

```sh
codex mcp add kakao -- "$HOME/.local/share/kakao-mcp/server/.venv/bin/kakao-mcp"
```

Reconnect MCP or start a new client session after registration. A successful handshake does not prove database access; run a read tool as well.

The installer refuses to replace an existing server checkout. It preserves an existing local config. Review changes before updating a working installation.

## Permissions and account identity

Reading requires Full Disk Access for the responsible host process. On ROCK, TCC attributed child commands to `~/.local/bin/herdr-core`, separately from `Herdr.app`. Determine the responsible process on each host; SSH access does not prove that a GUI host has permission. Sending additionally requires Accessibility permission for its host.

The patch writes an identity cache to `~/.cache/kakaocli/account.json`, mode 0600. It stores only an account ID and its hash. Every use validates the ID against the current account hash. Account switches and invalid cache values trigger recovery.

Keep `user_id` in `~/.config/kakao-mcp/config.json` set to `null`: the patched native reader derives the DB key internally, avoiding the upstream Python path that passes the key as a process argument. Do not copy DB keys or device-specific database paths between Macs. A known ID for the same account can seed a second Mac only after verifying its live account hash.

## Optional sending

Edit the existing `send` object in `~/.config/kakao-mcp/config.json`:

```json
{
  "enabled": true,
  "allowed_chats": {
    "chosen-alias": "Exact chatroom name"
  },
  "max_length": 1000,
  "confirm_ttl_seconds": 300
}
```

Reconnect the MCP server after changing configuration. Use `kakao_prepare_send`, review the recipient and exact message, and call `kakao_confirm_send` only after approval. Set `enabled` back to `false` to disable sending. Live sending was not tested during this installation.

## Verification and maintenance

The original MCP call exceeded its 60-second limit; standalone account discovery was stopped at 150 seconds. The patch removes per-candidate String/Array allocation and caches the recovered identity. On ROCK, first discovery/read took 54.975 seconds. Subsequent chat-list calls took 0.222–0.256 seconds; a two-day range query took 0.206 seconds. An 832-character message was complete and eight pages exactly matched a single full-range query.

Validation: 8 Swift tests and 46 MCP Python tests pass. New tests cover decimal carries, worker boundaries, deadlines, cache reuse, corrupt caches and account switches. No message contents, account IDs or DB keys belong in this repository.

After changing the patch or an upstream pin:

```sh
cd ~/.local/share/kakao-mcp/src/kakaocli
swift test -c release --disable-sandbox
install -m 0755 .build/release/kakaocli ~/.local/share/kakao-mcp/bin/kakaocli
cd ~/.local/share/kakao-mcp/server
.venv/bin/python -m pytest -q
```

Revalidate MCP discovery, live read/search, long-message completeness, pagination, and the disabled-send gate. Upstream `install-deps.sh` rejects a dirty reader checkout; reconcile the patch before updating rather than discarding it.

The SQLCipher 4.20.0 bottle installed on ROCK targets macOS 27. Its linker warning against the reader's macOS 14 deployment target does not establish support for older macOS. Build and verify dependencies on the target machine.
